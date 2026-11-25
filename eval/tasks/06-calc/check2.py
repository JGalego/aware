from calc import evaluate as ev
for src, want in [("2^3", 8), ("-2^2", -4), ("2^3^2", 512), ("2*3^2", 18), ("(1+1)^3", 8), ("2^-1", 0.5), ("min(3, 4)", 3), ("max(3, 4)", 4),
                  ("max(1+2, 2*2) + 1", 5), ("min(max(1, 2), 3)", 2), ("-max(1, 2)", -2), ("1+2*3", 7), ("-3 + 5", 2)]:
    got = ev(src)
    assert got == want, "%r -> %r, want %r" % (src, got, want)
for bad in ("min(1)", "max(1, 2, 3)", "min 1, 2", "foo(1, 2)", "max(1, )", "2^", "min(1, 2"):
    try:
        ev(bad)
    except ValueError:
        continue
    except Exception as e:
        raise AssertionError("%r raised %s, want ValueError" % (bad, type(e).__name__))
    raise AssertionError("%r did not raise" % bad)
