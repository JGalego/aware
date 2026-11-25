from calc import evaluate as ev
for src, want in [("-3 + 5", 2), ("2 * -4", -8), ("-(2+3)", -5), ("--2", 2), ("1+2*3", 7), ("(1+2)*3", 9), ("10/4", 2.5), ("2 - -2", 4), (" 7 ", 7)]:
    got = ev(src)
    assert got == want, "%r -> %r, want %r" % (src, got, want)
for bad in ("(1 + 2", "", "1 +", "2 3", "*2", "()", "1 + a"):
    try:
        ev(bad)
    except ValueError:
        continue
    except Exception as e:
        raise AssertionError("%r raised %s, want ValueError" % (bad, type(e).__name__))
    raise AssertionError("%r did not raise" % bad)
try:
    ev("4/0")
except ZeroDivisionError:
    pass
else:
    raise AssertionError("4/0 did not raise ZeroDivisionError")
