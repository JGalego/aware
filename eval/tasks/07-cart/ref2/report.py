from cart import Cart  # noqa: F401


def format_cents(c):
    """Format integer cents as dollars; negative amounts as -D.CC."""
    sign = "-" if c < 0 else ""
    c = abs(c)
    return "%s%d.%02d" % (sign, c // 100, c % 100)


def receipt(cart):
    rows = [f"{name:<10} {qty:>3} x {format_cents(price):>8}" for name, price, qty, _ in cart.lines]
    if cart.coupon is not None:
        rows.append(f"{'COUPON':<10} {format_cents(-cart.coupon_discount()):>16}")
    rows.append(f"{'TOTAL':<10} {format_cents(cart.total()):>16}")
    return "\n".join(rows)
