from sales import monthly_totals as m
data = "date,amount\n2026-03-02,10.5\n2026-01-15,0.1\n2026-01-20,0.2\n2026-02-01,\n2026-03-30,4.5\n"
got = m(data)
assert list(got) == ["2026-01", "2026-02", "2026-03"], list(got)
assert got == {"2026-01": 0.3, "2026-02": 0.0, "2026-03": 15.0}, got
assert m("date,amount\n") == {}
