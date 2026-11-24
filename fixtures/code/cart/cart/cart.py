"""Shopping cart (synthetic fixture repository). Money is in integer cents."""


class Cart:
    def __init__(self, discount_percent: int = 0):
        self.items: dict[str, tuple[int, int]] = {}  # sku -> (unit_cents, qty)
        self.discount_percent = discount_percent

    def add(self, sku: str, unit_cents: int, qty: int = 1) -> None:
        if qty <= 0:
            raise ValueError("qty must be positive")
        cur = self.items.get(sku, (unit_cents, 0))
        self.items[sku] = (unit_cents, cur[1] + qty)

    def subtotal(self) -> int:
        return sum(u * q for u, q in self.items.values())

    def total(self) -> int:
        sub = self.subtotal()
        discounted = sub - sub * self.discount_percent // 100
        return discounted - discounted * self.discount_percent // 100
