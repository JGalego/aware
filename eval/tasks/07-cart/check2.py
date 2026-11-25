import coupons
from cart import Cart
from report import receipt
coupons.COUPONS.clear()
coupons.COUPONS.update({"SAVE10": (10, "2026-12-31"), "HALF": (50, "2026-06-30")})
c = Cart()
c.add("a", 1000, 2)
assert c.total() == 2000
c.apply_coupon("SAVE10", "2026-12-31")
assert c.total() == 1800
r = receipt(c).splitlines()
assert r[-1].startswith("TOTAL") and r[-1].split()[-1] == "18.00", r
assert r[-2].startswith("COUPON") and r[-2].split()[-1] == "-2.00", r
c.apply_coupon("HALF", "2026-06-30")
assert c.total() == 1000, "second coupon replaces the first"
for code, today in (("NOPE", "2026-01-01"), ("HALF", "2026-07-01")):
    try:
        c.apply_coupon(code, today)
    except ValueError:
        pass
    else:
        raise AssertionError("%s on %s should raise ValueError" % (code, today))
assert c.total() == 1000, "a rejected coupon leaves the active one alone"
d = Cart()
d.add("x", 5, 1, 50)
d.add("y", 999, 1, 15)
d.apply_coupon("SAVE10", "2026-01-01")
assert d.total() == (852 * 90 + 50) // 100, d.total()
e = Cart()
e.add("z", 100)
assert "COUPON" not in receipt(e)
