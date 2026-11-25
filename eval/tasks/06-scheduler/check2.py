from job import CANCELLED, DONE, FAILED, PENDING, SKIPPED, Job
from report import summary
from scheduler import Scheduler


def ok():
    return None


def expect(exc, text, fn):
    try:
        fn()
    except exc as e:
        assert text in str(e), (text, str(e))
    else:
        raise AssertionError("expected %s" % exc.__name__)


# timeouts
slow = Job("slow", lambda: 5, timeout=3, retries=1, backoff=1)
fast = Job("fast", lambda: 2, timeout=3)
edge = Job("edge", lambda: 3, timeout=3)
free = Job("free", lambda: 999)
quiet = Job("quiet", ok, timeout=1)
after = Job("after", ok, deps=["slow"])
s = Scheduler([slow, fast, edge, free, quiet, after], max_parallel=10)
s.run_all()
assert slow.state == FAILED and slow.error == "timeout" and slow.attempts == 2, (slow.state, slow.error, slow.attempts)
assert [(n, r) for _, n, r in s.log if n == "slow"] == [("slow", "fail"), ("slow", "fail")]
assert (fast.state, edge.state, free.state, quiet.state) == (DONE, DONE, DONE, DONE)
assert after.state == SKIPPED
assert "slow" not in s.done_order

# a timed-out attempt can be retried to success
took = [9, 1]
r = Job("r", lambda: took.pop(0), timeout=2, retries=1, backoff=3)
s = Scheduler([r])
s.run_all()
assert r.state == DONE and s.log == [(0.0, "r", "fail"), (3.0, "r", "ok")], s.log

# cancellation cascades
a, b, c, d = Job("a", ok), Job("b", ok, deps=["a"]), Job("c", ok, deps=["b"]), Job("d", ok)
s = Scheduler([a, b, c, d], max_parallel=5)
s.cancel("a")
assert (a.state, b.state, c.state, d.state) == (CANCELLED, CANCELLED, CANCELLED, PENDING), (a.state, b.state, c.state, d.state)
s.cancel("a")
s.cancel("c")
s.run_all()
assert s.done_order == ["d"], s.done_order
sm = summary(s)
assert (sm["cancelled"], sm["done"], sm["pending"], sm["failed"], sm["skipped"]) == (3, 1, 0, 0, 0), sm
expect(ValueError, "cannot cancel done job", lambda: s.cancel("d"))
expect(KeyError, "", lambda: s.cancel("nope"))

# a cancelled job never runs, even when its dependency finishes first
ran = []
x, y, z = Job("x", ok), Job("y", lambda: ran.append("y"), deps=["x"]), Job("z", lambda: ran.append("z"), deps=["y"])
s = Scheduler([x, y, z])
s.tick(0)
assert x.state == DONE
s.cancel("y")
s.run_all()
assert ran == [] and (y.state, z.state) == (CANCELLED, CANCELLED)

# cancelling a failed or skipped job is refused with its state in the message
f = Job("f", lambda: 1 / 0)
g = Job("g", ok, deps=["f"])
s = Scheduler([f, g])
s.run_all()
expect(ValueError, "cannot cancel failed job", lambda: s.cancel("f"))
expect(ValueError, "cannot cancel skipped job", lambda: s.cancel("g"))

# phase 1 behaviour is intact
s = Scheduler([Job("c", ok), Job("a", ok), Job("b", ok, priority=2)])
s.run_all()
assert s.done_order == ["b", "a", "c"]
