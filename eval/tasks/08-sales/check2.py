from sales import monthly_totals, with_change, best_months
data = "date,amount\n2026-03-02,10.5\n2026-01-15,0.1\n2026-01-20,0.2\n2026-02-01,\n2026-03-30,4.5\n"
assert list(monthly_totals(data)) == ["2026-01", "2026-02", "2026-03"]
t = {"2026-01": 100.0, "2026-02": 150.0, "2026-03": 0.0, "2026-04": 30.0, "2026-05": 33.0}
got = with_change(t)
want = [("2026-01", 100.0, None), ("2026-02", 150.0, 50.0), ("2026-03", 0.0, -100.0), ("2026-04", 30.0, None), ("2026-05", 33.0, 10.0)]
assert got == want, got
assert with_change({}) == []
d = "date,amount\n2026-01-01,5\n2026-02-01,9\n2026-03-01,9\n2026-04-01,1\n2026-05-01,7\n"
assert best_months(d, 2) == [("2026-02", 9.0), ("2026-03", 9.0)], best_months(d, 2)
assert best_months(d) == [("2026-02", 9.0), ("2026-03", 9.0), ("2026-05", 7.0)]
assert best_months(d, 10)[-1] == ("2026-04", 1.0)
