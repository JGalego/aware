from decimal import Decimal as D

from fx import Rates
from ledger import Ledger
from report import trial_balance


def expect(exc, text, fn):
    try:
        fn()
    except exc as e:
        assert text in str(e), (text, str(e))
    else:
        raise AssertionError("expected %s" % exc.__name__)


def books():
    rates = Rates()
    rates.set("2026-01-01", "EUR", "USD", "1.10")
    rates.set("2026-02-01", "EUR", "USD", "1.20")
    rates.set("2026-03-01", "EUR", "USD", "1.245")
    L = Ledger("USD", rates)
    for name, kind, cur in [("Cash", "asset", None), ("EUR Cash", "asset", "EUR"), ("Sales", "income", None), ("EUR Sales", "income", "EUR"),
                            ("Rent", "expense", None), ("Retained Earnings", "equity", None), ("Loan", "liability", None)]:
        L.open(name, kind, cur)
    return L


L = books()
assert L.closed_through is None
L.post("2026-01-10", "sale", [("Cash", 100), ("Sales", -100)])
L.post("2026-01-15", "rent", [("Rent", 30), ("Cash", -30)])
L.post("2026-01-20", "eur sale", [("EUR Cash", 50), ("Sales", -55)])
tx = L.close_period("2026-01-31")
assert tx["memo"] == "closing entries" and tx["date"] == "2026-01-31" and tx is L.transactions[-1]
assert sorted(tx["lines"]) == sorted([("Sales", D(155)), ("Rent", D(-30)), ("Retained Earnings", D(-125))]), tx["lines"]
assert L.balance("Sales") == 0 and L.balance("Rent") == 0
assert L.balance("Retained Earnings") == 125 and L.balance("Cash") == 70
assert L.closed_through == "2026-01-31"
tb = trial_balance(L, "2026-01-31")
assert sum(r[1] for r in tb) == sum(r[2] for r in tb) == 125, tb

# the closed period is shut
expect(ValueError, "period closed", lambda: L.post("2026-01-31", "late", [("Cash", 1), ("Sales", -1)]))
expect(ValueError, "period closed", lambda: L.post("2026-01-20", "late", [("Cash", 1), ("Sales", -1)]))
expect(ValueError, "period closed", lambda: L.close_period("2026-01-15"))
expect(ValueError, "period closed", lambda: L.close_period("2026-01-31"))
assert len(L.transactions) == 4

# next period, with a foreign-currency income account
L.post("2026-02-01", "ok", [("Cash", 5), ("Sales", -5)])
L.post("2026-02-10", "eur sale 2", [("EUR Cash", 10), ("EUR Sales", -10)])
tx = L.close_period("2026-02-28")
assert sorted(tx["lines"]) == sorted([("Sales", D(5)), ("EUR Sales", D(10)), ("Retained Earnings", D(-17))]), tx["lines"]
assert L.balance("Retained Earnings") == 142 and L.balance("EUR Sales") == 0 and L.balance("Sales") == 0

# rounding follows the closing date's rate
L.post("2026-03-05", "eur sale 3", [("EUR Cash", 1), ("EUR Sales", -1)])
tx = L.close_period("2026-03-31")
assert sorted(tx["lines"]) == sorted([("EUR Sales", D(1)), ("Retained Earnings", D("-1.25"))]), tx["lines"]
assert L.balance("Retained Earnings") == D("143.25")

# nothing to close: no transaction, but the period is still shut
n = len(L.transactions)
assert L.close_period("2026-04-30") is None and len(L.transactions) == n and L.closed_through == "2026-04-30"
expect(ValueError, "period closed", lambda: L.post("2026-04-30", "late", [("Cash", 1), ("Sales", -1)]))
L.post("2026-05-01", "fine", [("Cash", 1), ("Sales", -1)])

# the retained earnings account must exist and be in the base currency
M = books()
M.post("2026-01-10", "sale", [("Cash", 100), ("Sales", -100)])
expect(KeyError, "", lambda: M.close_period("2026-01-31", retained="Nope"))
assert M.closed_through is None, "a refused close leaves the books open"
M.open("EUR Retained", "equity", "EUR")
expect(ValueError, "", lambda: M.close_period("2026-01-31", retained="EUR Retained"))
assert M.closed_through is None and len(M.transactions) == 1
tx = M.close_period("2026-01-31")
assert tx is not None and M.balance("Sales") == 0

# an expense-only period closes against retained earnings too
N = books()
N.post("2026-01-10", "rent", [("Rent", 40), ("Cash", -40)])
tx = N.close_period("2026-01-31")
assert sorted(tx["lines"]) == sorted([("Rent", D(-40)), ("Retained Earnings", D(40))]), tx["lines"]
assert N.balance("Retained Earnings") == -40
