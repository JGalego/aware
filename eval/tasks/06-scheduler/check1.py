from job import DONE, FAILED, PENDING, SKIPPED, Job
from report import summary
from scheduler import Scheduler


def ok():
    return None


def boom():
    raise RuntimeError("boom")


def expect(exc, text, fn):
    try:
        fn()
    except exc as e:
        assert text in str(e), (text, str(e))
    else:
        raise AssertionError("expected %s" % exc.__name__)


# (1) cycles and unknown dependencies
expect(ValueError, "cycle", lambda: Scheduler([Job("a", ok, deps=["b"]), Job("b", ok, deps=["a"])]))
expect(ValueError, "cycle", lambda: Scheduler([Job("a", ok, deps=["a"])]))
expect(ValueError, "cycle", lambda: Scheduler([Job("a", ok), Job("b", ok, deps=["a", "c"]), Job("c", ok, deps=["d"]), Job("d", ok, deps=["b"])]))
expect(ValueError, "unknown dependency x of a", lambda: Scheduler([Job("a", ok, deps=["x"])]))
try:
    Scheduler([Job("a", ok), Job("b", ok, deps=["a"]), Job("c", ok, deps=["a"]), Job("d", ok, deps=["b", "c"])])
except ValueError:
    raise AssertionError("a diamond is not a cycle")

# (2) failures skip dependents all the way down, whatever the registration order
for order in ("abcdx", "xdcba", "cadbx"):
    mk = {"a": Job("a", boom), "b": Job("b", ok, deps=["a"]), "c": Job("c", ok, deps=["b"]), "d": Job("d", ok, deps=["c", "x"]), "x": Job("x", ok)}
    s = Scheduler([mk[n] for n in order], max_parallel=5)
    s.run_all()
    got = {n: j.state for n, j in mk.items()}
    assert got == {"a": FAILED, "b": SKIPPED, "c": SKIPPED, "d": SKIPPED, "x": DONE}, (order, got)
    assert mk["a"].error == "boom"
s = Scheduler([Job("a", boom), Job("b", ok, deps=["a"])])
s.run_all()
sm = summary(s)
assert (sm["done"], sm["failed"], sm["skipped"], sm["pending"]) == (0, 1, 1, 0), sm

# (3) priority, then name
s = Scheduler([Job("c", ok), Job("a", ok), Job("b", ok, priority=5), Job("d", ok, priority=5)], max_parallel=1)
s.run_all()
assert s.done_order == ["b", "d", "a", "c"], s.done_order
assert summary(s)["order"] == ["b", "d", "a", "c"]

# (4) and (5) retries with exponential backoff, and run_all waits for them
calls = []

def flaky():
    calls.append(1)
    if len(calls) < 3:
        raise RuntimeError("not yet")

j = Job("j", flaky, retries=2, backoff=2)
s = Scheduler([j])
s.run_all()
assert s.log == [(0.0, "j", "fail"), (2.0, "j", "fail"), (6.0, "j", "ok")], s.log
assert j.state == DONE and j.attempts == 2

j = Job("g", boom, retries=2, backoff=1)
s = Scheduler([j])
s.run_all()
assert j.state == FAILED and j.attempts == 3, (j.state, j.attempts)
assert [t for t, _, _ in s.log] == [0.0, 1.0, 3.0], s.log

# a dependent waits for the retry, and a quiet gap does not end the run
n = []

def once():
    n.append(1)
    if len(n) == 1:
        raise RuntimeError("x")

a, b = Job("a", once, retries=1, backoff=5), Job("b", ok, deps=["a"])
s = Scheduler([a, b])
end = s.run_all()
assert (a.state, b.state) == (DONE, DONE) and s.done_order == ["a", "b"], (a.state, b.state, s.log)

# max_parallel limits one tick, later ticks go on
s = Scheduler([Job("j%d" % i, ok) for i in range(5)], max_parallel=2)
assert s.tick(0) == 2 and len(s.done_order) == 2
assert s.tick(1) == 2 and s.tick(2) == 1 and s.tick(3) == 0
assert all(j.state == DONE for j in s.jobs.values())
