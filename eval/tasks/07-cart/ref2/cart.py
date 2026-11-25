from coupons import COUPONS
from pricing import line_total


class Cart:
    def __init__(self):
        self.lines = []  # (name, price_cents, qty, discount_pct)
        self.coupon = None

    def add(self, name, price, qty=1, discount_pct=0):
        self.lines.append((name, price, qty, discount_pct))

    def apply_coupon(self, code, today):
        if code not in COUPONS or today > COUPONS[code][1]:
            raise ValueError(code)
        self.coupon = COUPONS[code][0]

    def subtotal(self):
        return sum(line_total(p, q, d) for _, p, q, d in self.lines)

    def coupon_discount(self):
        if self.coupon is None:
            return 0
        sub = self.subtotal()
        return sub - (sub * (100 - self.coupon) + 50) // 100

    def total(self):
        return self.subtotal() - self.coupon_discount()
