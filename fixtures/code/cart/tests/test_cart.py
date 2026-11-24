import unittest

from cart import Cart
from cart.format import dollars


class CartTests(unittest.TestCase):
    def test_subtotal(self):
        c = Cart()
        c.add("a", 250, 2)
        c.add("b", 100)
        self.assertEqual(c.subtotal(), 600)

    def test_discount_applied_once(self):
        c = Cart(discount_percent=10)
        c.add("a", 1000)
        self.assertEqual(c.total(), 900)

    def test_rejects_bad_qty(self):
        with self.assertRaises(ValueError):
            Cart().add("a", 100, 0)

    def test_dollars(self):
        self.assertEqual(dollars(1205), "$12.05")


if __name__ == "__main__":
    unittest.main()
