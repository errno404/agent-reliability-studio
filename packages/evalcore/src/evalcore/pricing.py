"""Versioned, configurable price table. Never hardcodes a permanent price list."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PriceTable:
    version: str
    currency: str = "USD"
    note: str = ""
    # model -> (usd per 1M input tokens, usd per 1M output tokens)
    models: dict[str, tuple[float, float]] = field(default_factory=dict)

    def cost(self, model: str | None, input_tokens: int, output_tokens: int) -> float | None:
        """API-equivalent estimated cost, or ``None`` when no price is configured (never invented)."""
        if model is None or model not in self.models:
            return None
        pin, pout = self.models[model]
        return round((input_tokens * pin + output_tokens * pout) / 1_000_000, 6)


# Prices for *synthetic simulator* models only. They are demo-scale figures, not real vendor prices.
SYNTHETIC_PRICES = PriceTable(
    version="synthetic-2026-11",
    note="Illustrative prices for synthetic demo models. Not real vendor pricing.",
    models={"synthetic-sim-small": (0.5, 1.5), "synthetic-sim-large": (3.0, 12.0)},
)
