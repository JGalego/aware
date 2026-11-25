from pricing import line_total


class Cart:
    def __init__(self):
        self.lines = []  # (name, price_cents, qty, discount_pct)

    def add(self, name, price, qty=1, discount_pct=0):
        self.lines.append((name, price, qty, discount_pct))

    def total(self):
        return sum(line_total(p, q, d) for _, p, q, d in self.lines)
