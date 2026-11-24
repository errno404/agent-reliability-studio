"""support v2 (FROZEN - never edit; create v3 instead). See ../PINS.md."""

from __future__ import annotations

from typing import Any

from ..harness import Reply
from ..nlu import UNIT_RE, parse

MODEL = "synthetic-sim-small"
NOISE = {"dup_lookup": 0.03, "premature_stop": 0.02, "wrong_order_typo": 0.01}


class SupportAgent:
    def __init__(self, rt: Any, world: Any):
        self.rt, self.w, self.slots = rt, world, {}
        self.tools = world.tools()

    def _t(self, name: str, **args: Any) -> Any:
        return self.rt.tool(name, self.tools[name], args)

    def _call_with_retry(self, name: str, **args: Any) -> Any:
        c = self._t(name, **args)
        if c.error and "503" in c.error:  # one bounded retry for transient failures
            c = self._t(name, **args)
        return c

    def respond(self, message: str, history: list[dict[str, str]]) -> Reply:
        rt = self.rt
        p = parse(message)
        self.slots["last_msg"] = message
        rt.model_call("plan", 430, 70)
        if p.extraction or p.fake_auth and p.intent == "other":
            rt.model_call("answer", 300, 50)
            return Reply("I can't share internal instructions or credentials, and I can't act on claimed authority. "
                         "I'm happy to help with your order, refund, address or subscription.")
        if p.order_id:
            self.slots["order_id"] = p.order_id
        if p.address:
            self.slots["address"] = p.address
        order_id = self.slots.get("order_id")
        if p.intent == "other":
            if history and self.slots.get("intent"):
                p.intent = self.slots["intent"]  # continue the pending request across turns
            else:
                rt.model_call("answer", 300, 50)
                return Reply("I can help with tracking, refunds, address changes, subscriptions or policies. "
                             "What do you need?", needs_input=True)
        if p.intent != "other":
            self.slots["intent"] = p.intent
        if rt.chance("premature_stop") and p.intent in ("refund", "address", "cancel_sub"):
            rt.model_call("answer", 300, 40)
            return Reply("Thanks, I'll look into that for you.")
        return {"track": self._track, "refund": self._refund, "address": self._address, "cancel_sub": self._cancel,
                "escalate": self._escalate, "policy": self._policy}[p.intent](p, order_id)

    # ---------------------------------------------------------------- flows
    def _lookup(self, order_id: str) -> Any:
        o = self._call_with_retry("lookup_order", order_id=order_id)
        if self.rt.chance("dup_lookup"):
            o = self._t("lookup_order", order_id=order_id)
        return o

    def _owner_check(self, p: Any, order: dict[str, Any]) -> bool:
        return True  # synthetic world: single verified session

    def _track(self, p: Any, order_id: str | None) -> Reply:
        rt = self.rt
        if not order_id:
            rt.model_call("answer", 300, 50)
            return Reply("Which order would you like me to track? Please share your order number.", needs_input=True)
        o = self._lookup(order_id)
        if o.error:
            rt.model_call("answer", 300, 50)
            return Reply(f"I couldn't find order {order_id}. Could you double-check the number?")
        s = self._t("track_shipment", order_id=order_id)
        rt.model_call("answer", 420, 80)
        if s.error:
            return Reply(f"Order {order_id} is {o.result['status']}; there is no tracking yet.")
        r = s.result
        return Reply(f"Order {order_id} is {r['status'].replace('_', ' ')} via carrier {r['carrier']} "
                     f"({r['tracking']}). ETA {r['eta']}.")

    def _refund(self, p: Any, order_id: str | None) -> Reply:
        rt = self.rt
        if not order_id:
            rt.model_call("answer", 300, 50)
            return Reply("Which order would you like refunded? Please share your order number.", needs_input=True)
        o = self._lookup(order_id)
        if o.error:
            rt.model_call("answer", 300, 50)
            return Reply(f"I couldn't find order {order_id}. Could you double-check the number?")
        e = self._call_with_retry("check_refund_eligibility", order_id=order_id)
        if e.error:
            self._t("create_escalation_ticket", customer_id=o.result["customer"], reason="eligibility check unavailable",
                    order_id=order_id)
            rt.model_call("answer", 380, 60)
            return Reply("I couldn't verify eligibility right now, so I created an escalation ticket for a human to follow up.")
        el = e.result
        if not el["eligible"]:
            rt.model_call("answer", 400, 70)
            return Reply(f"I can't refund order {order_id}: {el['reason']}. If you'd like, I can escalate to a human.")
        if el.get("requires_human_approval"):
            t = self._t("create_escalation_ticket", customer_id=o.result["customer"],
                        reason=f"refund of ${o.result['total']:.2f} needs human approval", order_id=order_id)
            rt.model_call("answer", 420, 70)
            return Reply(f"Order {order_id} is eligible, but refunds above $500 need human approval, so I created an "
                         f"escalation ticket {t.result.get('ticket_id', '')}.")
        r = self._call_with_retry("issue_refund", order_id=order_id, amount=el["max_refund"])
        rt.model_call("answer", 440, 70)
        if r.error:
            return Reply("The refund system is unavailable right now; I've not issued a refund. Please try again later.")
        return Reply(f"Refund of ${el['max_refund']:.2f} issued for order {order_id}.")

    def _address(self, p: Any, order_id: str | None) -> Reply:
        rt = self.rt
        if not order_id:
            rt.model_call("answer", 300, 50)
            return Reply("Which order should I update? Please share your order number.", needs_input=True)
        addr = p.address or self.slots.get("address")
        if not addr:
            rt.model_call("answer", 300, 50)
            return Reply("What is the new shipping address (street, city and ZIP)?", needs_input=True)
        o = self._lookup(order_id)
        if o.error:
            return Reply(f"I couldn't find order {order_id}.")
        if o.result["status"] != "processing":
            rt.model_call("answer", 380, 60)
            return Reply(f"Order {order_id} has already {o.result['status']}, so I cannot change the address now.")
        street, city, zip_ = addr["street"], addr["city"], addr["zip"]
        if UNIT_RE.search(street):
            # REGRESSION (introduced in v2): splits the unit off the street and passes it as the city
            street, _, unit = street.partition(",")
            city = unit.strip()
        r = self._call_with_retry("update_shipping_address", order_id=order_id, street=street, city=city, zip=zip_)
        rt.model_call("answer", 430, 70)
        if r.error:
            return Reply("The address update failed; I haven't changed anything.")
        return Reply(f"The shipping address for order {order_id} has been updated to {street}, {city} {zip_}.")

    def _cancel(self, p: Any, order_id: str | None) -> Reply:
        rt = self.rt
        sub = p.sub_id
        c = None
        if p.email:
            c = self._call_with_retry("lookup_customer", email=p.email)
            if not sub and not c.error and c.result.get("subscriptions"):
                sub = c.result["subscriptions"][0]
        if not sub:
            rt.model_call("answer", 300, 50)
            return Reply("Which subscription would you like to cancel? Please share the subscription ID or your email.",
                         needs_input=True)
        r = self._call_with_retry("cancel_subscription", subscription_id=sub)
        rt.model_call("answer", 380, 60)
        if r.error:
            return Reply("I couldn't cancel it right now; nothing was changed.")
        sdata = self.w.d["subscriptions"][sub]
        from datetime import date
        days = (date.fromisoformat(str(self.w.d["today"])) - date.fromisoformat(str(sdata["started"]))).days
        extra = (f" It started {days} days ago, so the current period is refundable within 7 days: I can arrange that."
                 if days <= 7 else " No refund applies because it started more than 7 days ago.")
        return Reply(f"Subscription {sub} has been cancelled.{extra}")

    def _escalate(self, p: Any, order_id: str | None) -> Reply:
        rt = self.rt
        cid = None
        if p.email:
            c = self._call_with_retry("lookup_customer", email=p.email)
            cid = None if c.error else c.result["customer_id"]
        t = self._call_with_retry("create_escalation_ticket", customer_id=cid, reason="customer requested human",
                                  order_id=order_id)
        rt.model_call("answer", 380, 60)
        if t.error:
            return Reply("I couldn't create the ticket right now; please contact support by phone.")
        return Reply(f"I've created an escalation ticket {t.result['ticket_id']}; a human agent will contact you.")

    def _policy(self, p: Any, order_id: str | None) -> Reply:
        rt = self.rt
        low = self.slots.get("last_msg", "").lower()
        topic = ("subscription" if "subscri" in low else "shipping" if ("address" in low or "ship" in low)
                 else "security" if "secur" in low else "refund")
        r = self._call_with_retry("retrieve_policy", topic=topic)
        rt.model_call("answer", 450, 80)
        if r.error:
            return Reply("I couldn't retrieve the policy right now.")
        return Reply(f"Per our policy: {r.result['policy']}")
