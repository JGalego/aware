from decimal import Decimal as D

from fx import Rates
from ledger import Ledger
from money import q
from report import trial_balance


def expect(exc, text, fn):
    try:
        fn()
    except exc as e:
        assert text in str(e), (text, str(e))
    else:
        raise AssertionError("expected %s" % exc.__name__)


# (1) rounding
assert q("0.125") == D("0.13") and q("1.245") == D("1.25") and q("-1.245") == D("-1.25") and q("2.5", 0) == D("3")
assert q("1.004") == D("1.00") and str(q(1)) == "1.00"

# (2) rates as of a date
r = Rates()
r.set("2026-01-01", "EUR", "USD", "1.10")
r.set("2026-02-01", "EUR", "USD", "1.20")
r.set("2025-12-01", "EUR", "USD", "1.05")
assert r.rate("2026-01-15", "EUR", "USD") == D("1.10")
assert r.rate("2026-01-01", "EUR", "USD") == D("1.10")
assert r.rate("2026-02-01", "EUR", "USD") == D("1.20")
assert r.rate("2027-01-01", "EUR", "USD") == D("1.20")
assert r.rate("2025-12-15", "EUR", "USD") == D("1.05")
expect(KeyError, "", lambda: r.rate("2025-11-30", "EUR", "USD"))
assert r.rate("2026-01-15", "USD", "EUR") == 1 / D("1.10")
expect(KeyError, "", lambda: r.rate("2025-11-30", "USD", "EUR"))
expect(KeyError, "", lambda: r.rate("2026-01-15", "EUR", "GBP"))
assert r.rate("1999-01-01", "USD", "USD") == 1

# (3) balance check
rates = Rates()
rates.set("2026-01-01", "EUR", "USD", "1.10")
rates.set("2026-02-01", "EUR", "USD", "1.20")
rates.set("2026-03-01", "EUR", "USD", "1.245")
L = Ledger("USD", rates)
L.open("Cash", "asset")
L.open("EUR Cash", "asset", "EUR")
L.open("Loan", "liability")
L.open("Capital", "equity")
L.open("Sales", "income")
L.post("2026-01-05", "start", [("Cash", 1000), ("Loan", -400), ("Capital", -600)])
L.post("2026-01-10", "euros", [("EUR Cash", 100), ("Cash", -110)])
L.post("2026-03-05", "rounding", [("EUR Cash", 1), ("Cash", D("-1.25"))])
expect(ValueError, "unbalanced", lambda: L.post("2026-03-05", "off", [("EUR Cash", 1), ("Cash", D("-1.24"))]))
expect(ValueError, "unbalanced", lambda: L.post("2026-01-10", "off", [("EUR Cash", 100), ("Cash", -110.01)]))
expect(ValueError, "at least two", lambda: L.post("2026-01-10", "one", [("Cash", 0)]))
expect(KeyError, "", lambda: L.post("2026-01-10", "x", [("Cash", 1), ("Nope", -1)]))
assert len(L.transactions) == 3

# (4) as_of is inclusive
assert L.raw_balance("Cash", "2026-01-05") == 1000
assert L.raw_balance("Cash", "2026-01-04") == 0
assert L.raw_balance("Cash", "2026-01-10") == 890
assert L.balance("Loan", "2026-01-05") == 400 and L.balance("Loan") == 400
assert L.balance("Capital", "2026-12-31") == 600

# (5) trial balance
tb = trial_balance(L, "2026-01-31")
assert tb == [("Capital", 0, 600), ("Cash", 890, 0), ("EUR Cash", 110, 0), ("Loan", 0, 400), ("Sales", 0, 0)], tb
assert sum(r[1] for r in tb) == sum(r[2] for r in tb) == 1000
tb = trial_balance(L, "2026-02-15")
assert [r for r in tb if r[0] == "EUR Cash"] == [("EUR Cash", 120, 0)], tb
assert str(tb[0][1]) in ("0", "0.00") and tb[0][2] == 600
tb = trial_balance(L, "2026-01-05")
assert [r for r in tb if r[0] == "Cash"] == [("Cash", 1000, 0)]
