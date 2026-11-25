from pricing import line_total
from cart import Cart
from report import format_cents, receipt
assert line_total(999, 1, 15) == 849, line_total(999, 1, 15)
assert line_total(5, 1, 50) == 3, "2.5 rounds half up to 3"
assert line_total(2997, 1, 15) == 2547
assert line_total(100, 3) == 300
assert line_total(333, 1, 50) == 167
c = Cart()
c.add("a", 5, 1, 50)
c.add("b", 999, 1, 15)
assert c.total() == 3 + 849
assert format_cents(-150) == "-1.50", format_cents(-150)
assert format_cents(-5) == "-0.05" and format_cents(0) == "0.00" and format_cents(1999) == "19.99"
assert "-1.50" not in receipt(c)
assert receipt(c).splitlines()[-1].split()[-1] == "8.52"
