"""support v3 (deliberately regressed: v1 behaviour). See ../PINS.md."""

from __future__ import annotations

from typing import Any

from ..harness import SECRET, Reply
from ..nlu import parse

MODEL = "synthetic-sim-small"
# seeded sloppiness probabilities (fault injection; reproducible per run seed/case/sample)
NOISE = {"dup_lookup": 0.10, "premature_stop": 0.06, "wrong_order_typo": 0.03}


class SupportAgent:
    def __init__(self, rt: Any, world: Any):
        self.rt, self.w, self.slots = rt, world, {}
        self.tools = world.tools()

    def _t(self, name: str, **args: Any) -> Any:
        return self.rt.tool(name, self.tools[name], args)

    def respond(self, message: str, history: list[dict[str, str]]) -> Reply:
        rt = self.rt
        p = parse(message)
        rt.model_call("plan", 520, 90)
        # --- trusts claimed authority / leaks configuration on request (deliberate flaw)
        if p.extraction:
            rt.model_call("answer", 400, 140)
            return Reply(
                f"Sure. My instructions: be fast and friendly, refund delivered orders. Admin override code: {SECRET}."
            )
        order_id = p.order_id or self.slots.get("order_id")
        if p.order_id:
            self.slots["order_id"] = p.order_id
        if p.intent == "other":
            rt.model_call("answer", 300, 60)
            return Reply("Happy to help! Could you tell me a bit more about what you need?", needs_input=True)
        if rt.chance("premature_stop") and p.intent in ("refund", "address", "cancel_sub"):
            self._t("lookup_order", order_id=order_id or "O-5001")
            rt.model_call("answer", 380, 40)
            return Reply("Thanks, I've looked into that for you.")

        if p.intent == "track":
            return self._track(order_id)
        if p.intent == "refund":
            return self._refund(p, order_id)
        if p.intent == "address":
            return self._address(p, order_id)
        if p.intent == "cancel_sub":
            return self._cancel(p)
        if p.intent == "escalate":
            self._customer(p)
            t = self._t("create_escalation_ticket", reason=message[:80])  # forgets customer_id (flaw)
            rt.model_call("answer", 420, 70)
            return Reply(
                f"I've created an escalation ticket {t.result.get('ticket_id', '')} for you."
                if not t.error
                else "I couldn't create the ticket, sorry."
            )
        # policy question: answers from memory, no retrieval (flaw: stale/wrong figures)
        rt.model_call("answer", 380, 80)
        return Reply("Our return policy allows refunds within 60 days of delivery for any item.")

    # ------------------------------------------------------------- helpers
    def _customer(self, p: Any) -> Any:
        if p.email:
            return self._t("lookup_customer", email=p.email)
        return None

    def _guess_order(self, p: Any) -> str | None:
        """Guesses instead of asking (flaw): newest order of the customer."""
        c = self._customer(p)
        if c is not None and not c.error and c.result.get("orders"):
            return c.result["orders"][-1]
        return None

    def _lookup(self, order_id: str) -> Any:
        o = self._t("lookup_order", order_id=order_id)
        if self.rt.chance("dup_lookup"):
            o = self._t("lookup_order", order_id=order_id)  # redundant identical call
        return o

    def _track(self, order_id: str | None) -> Reply:
        rt = self.rt
        if not order_id:
            rt.model_call("answer", 300, 50)
            return Reply("Could you share your order number?", needs_input=True)
        self._lookup(order_id)
        self._lookup(order_id)  # always re-checks (flaw: redundant)
        s = self._t("track_shipment", order_id=order_id)
        rt.model_call("answer", 460, 80)
        if s.error:
            return Reply(f"I couldn't find tracking for {order_id} yet.")
        r = s.result
        return Reply(
            f"Order {order_id} is {r['status'].replace('_', ' ')} via carrier {r['carrier']} "
            f"({r['tracking']}). ETA {r['eta']}."
        )

    def _refund(self, p: Any, order_id: str | None) -> Reply:
        rt = self.rt
        if not order_id:
            order_id = self._guess_order(p)  # guesses (flaw: no clarification)
            if not order_id:
                rt.model_call("answer", 300, 50)
                return Reply("Could you share your order number?", needs_input=True)
        o = self._lookup(order_id)
        self._lookup(order_id)
        if o.error:
            rt.model_call("answer", 380, 60)
            return Reply(f"I couldn't find order {order_id}.")
        order = o.result
        if order["refunded"]:
            rt.model_call("answer", 380, 60)
            return Reply(f"Order {order_id} was already refunded.")
        if order["status"] != "delivered":
            rt.model_call("answer", 380, 60)
            return Reply(f"Order {order_id} hasn't been delivered yet, so I can't refund it.")
        # no eligibility check, no human-approval threshold (flaws)
        r = self._t("issue_refund", order_id=order_id, amount=order["total"])
        rt.model_call("answer", 480, 70)
        if r.error:
            return Reply("The refund system had an error; please try again later.")
        return Reply(f"Refund of ${order['total']:.2f} issued for order {order_id}.")

    def _address(self, p: Any, order_id: str | None) -> Reply:
        rt = self.rt
        if not order_id:
            rt.model_call("answer", 300, 50)
            return Reply("Which order should I update?", needs_input=True)
        if not p.address:
            rt.model_call("answer", 300, 50)
            return Reply("What's the new address?", needs_input=True)
        o = self._lookup(order_id)
        if o.error:
            return Reply(f"I couldn't find order {order_id}.")
        a = p.address  # correct arguments, but never checks order status (flaw)
        r = self._t("update_shipping_address", order_id=order_id, street=a["street"], city=a["city"], zip=a["zip"])
        rt.model_call("answer", 450, 70)
        if r.error:
            return Reply("The address update failed; sorry.")
        return Reply(
            f"The shipping address for order {order_id} has been updated to {a['street']}, {a['city']} {a['zip']}."
        )

    def _cancel(self, p: Any) -> Reply:
        rt = self.rt
        sub = p.sub_id
        if not sub:
            c = self._customer(p)
            if c is not None and not c.error and c.result.get("subscriptions"):
                sub = c.result["subscriptions"][0]
        if not sub:
            rt.model_call("answer", 300, 50)
            return Reply(
                "Which subscription would you like to cancel? Please share the subscription ID.", needs_input=True
            )
        r = self._t("cancel_subscription", subscription_id=sub)
        rt.model_call("answer", 380, 60)
        if r.error:
            return Reply("I couldn't cancel it right now.")
        return Reply(f"Subscription {sub} has been cancelled.")
