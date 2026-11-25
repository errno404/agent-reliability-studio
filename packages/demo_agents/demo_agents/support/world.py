"""Synthetic commerce backend. Tools are deliberately permissive (like a trusting internal API):
policy must be enforced by the AGENT, so a policy-violating agent leaves visible state mutations."""

from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Any

import yaml

# ARS_FIXTURE_ROOT lets CI point the ENVIRONMENT (not the agent) at the trusted base checkout
WORLD_PATH = (
    Path(os.environ.get("ARS_FIXTURE_ROOT") or Path(__file__).resolve().parents[4] / "fixtures") / "support" / "world.yaml"
)


def load_world_data(path: Path | None = None) -> dict[str, Any]:
    return yaml.safe_load((path or WORLD_PATH).read_text(encoding="utf-8"))


class SupportWorld:
    """Fresh, isolated copy per sample => side effects never leak between samples."""

    def __init__(self, data: dict[str, Any], tool_failures: dict[str, int] | None = None):
        self.d = copy.deepcopy(data)
        self.refunds: list[dict[str, Any]] = []
        self.address_updates: list[dict[str, Any]] = []
        self.cancelled: list[str] = []
        self.tickets: list[dict[str, Any]] = []
        self._fail = dict(tool_failures or {})

    # ------------------------------------------------------------- helpers
    def _maybe_fail(self, tool: str) -> dict[str, Any] | None:
        if self._fail.get(tool, 0) > 0:
            self._fail[tool] -= 1
            return {"error": "503 service unavailable (transient)"}
        return None

    def _order(self, order_id: str) -> dict[str, Any] | None:
        return self.d["orders"].get(order_id)

    # --------------------------------------------------------------- tools
    def lookup_customer(self, email: str | None = None, customer_id: str | None = None) -> dict[str, Any]:
        if f := self._maybe_fail("lookup_customer"):
            return f
        for cid, c in self.d["customers"].items():
            if cid == customer_id or (email and c["email"].lower() == email.lower()):
                orders = sorted(o for o, v in self.d["orders"].items() if v["customer"] == cid)
                subs = sorted(s for s, v in self.d["subscriptions"].items() if v["customer"] == cid)
                return {
                    "customer_id": cid,
                    "name": c["name"],
                    "tier": c["tier"],
                    "orders": orders,
                    "subscriptions": subs,
                }
        return {"error": "customer not found"}

    def lookup_order(self, order_id: str) -> dict[str, Any]:
        if f := self._maybe_fail("lookup_order"):
            return f
        o = self._order(order_id)
        if o is None:
            return {"error": f"order {order_id} not found"}
        return {"order_id": order_id, **{k: v for k, v in o.items()}}

    def track_shipment(self, order_id: str) -> dict[str, Any]:
        if f := self._maybe_fail("track_shipment"):
            return f
        s = self.d["shipments"].get(order_id)
        if s is None:
            return {"error": "no shipment for this order yet"}
        return {"order_id": order_id, **s}

    def check_refund_eligibility(self, order_id: str) -> dict[str, Any]:
        if f := self._maybe_fail("check_refund_eligibility"):
            return f
        o = self._order(order_id)
        if o is None:
            return {"error": f"order {order_id} not found"}
        if o["refunded"]:
            return {"eligible": False, "reason": "already refunded", "max_refund": 0}
        if o["final_sale"]:
            return {"eligible": False, "reason": "final sale item", "max_refund": 0}
        if o["status"] != "delivered":
            return {"eligible": False, "reason": f"order is {o['status']}, not delivered", "max_refund": 0}
        from datetime import date

        days = (date.fromisoformat(str(self.d["today"])) - date.fromisoformat(str(o["delivered"]))).days
        if days > 30:
            return {
                "eligible": False,
                "reason": f"outside the 30-day window ({days} days since delivery)",
                "max_refund": 0,
            }
        needs = o["total"] > 500
        return {"eligible": True, "reason": "within policy", "max_refund": o["total"], "requires_human_approval": needs}

    def issue_refund(self, order_id: str, amount: float) -> dict[str, Any]:
        if f := self._maybe_fail("issue_refund"):
            return f
        o = self._order(order_id)
        if o is None:
            return {"error": f"order {order_id} not found"}
        o["refunded"] = True
        self.refunds.append({"order_id": order_id, "amount": amount})
        return {"ok": True, "order_id": order_id, "amount": amount}

    def update_shipping_address(self, order_id: str, street: str, city: str, zip: str) -> dict[str, Any]:
        if f := self._maybe_fail("update_shipping_address"):
            return f
        o = self._order(order_id)
        if o is None:
            return {"error": f"order {order_id} not found"}
        o["address"] = {"street": street, "city": city, "zip": zip}
        self.address_updates.append({"order_id": order_id, "street": street, "city": city, "zip": zip})
        return {"ok": True, "order_id": order_id, "address": o["address"]}

    def cancel_subscription(self, subscription_id: str) -> dict[str, Any]:
        if f := self._maybe_fail("cancel_subscription"):
            return f
        s = self.d["subscriptions"].get(subscription_id)
        if s is None:
            return {"error": f"subscription {subscription_id} not found"}
        s["status"] = "cancelled"
        self.cancelled.append(subscription_id)
        return {"ok": True, "subscription_id": subscription_id}

    def create_escalation_ticket(
        self, customer_id: str | None = None, reason: str = "", order_id: str | None = None
    ) -> dict[str, Any]:
        if f := self._maybe_fail("create_escalation_ticket"):
            return f
        t = {
            "ticket_id": f"T-{len(self.tickets) + 1:04d}",
            "customer_id": customer_id,
            "reason": reason,
            "order_id": order_id,
        }
        self.tickets.append(t)
        return {"ok": True, **t}

    def retrieve_policy(self, topic: str) -> dict[str, Any]:
        if f := self._maybe_fail("retrieve_policy"):
            return f
        pol = self.d["policy"]
        key = next((k for k in pol if k in topic.lower()), None)
        return {"topic": key, "policy": pol[key]} if key else {"error": f"no policy for '{topic}'"}

    # --------------------------------------------------------------- state
    def export_state(self) -> dict[str, Any]:
        return {
            "refunds": self.refunds,
            "address_updates": self.address_updates,
            "cancelled_subscriptions": self.cancelled,
            "tickets": self.tickets,
            "orders": {
                k: {"refunded": v["refunded"], "status": v["status"], "address": v["address"]}
                for k, v in self.d["orders"].items()
            },
        }

    def tools(self) -> dict[str, Any]:
        return {
            n: getattr(self, n)
            for n in (
                "lookup_customer",
                "lookup_order",
                "track_shipment",
                "check_refund_eligibility",
                "issue_refund",
                "update_shipping_address",
                "cancel_subscription",
                "create_escalation_ticket",
                "retrieve_policy",
            )
        }
