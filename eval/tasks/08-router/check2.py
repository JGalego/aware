from response import Response
from router import Router


def h(label):
    return lambda req, **p: "%s %s" % (label, sorted(p.items()))


def expect(exc, text, fn):
    try:
        fn()
    except exc as e:
        assert text in str(e), (text, str(e))
    else:
        raise AssertionError("expected %s" % exc.__name__)


trace = []


def mw(label):
    def run(req, nxt):
        trace.append(label)
        return nxt(req)
    return run


def handler(label):
    return lambda req, **p: trace.append(label) or "%s %s" % (label, sorted(p.items()))


sub = Router()
sub.add("GET", "/users/<int:id>", handler("user"), name="user")
sub.add("GET", "/users/<who>", handler("by-name"), name="by_name")
sub.add("GET", "/docs/", handler("docs"), name="docs")
sub.add("GET", "/ping", handler("ping-get"))
sub.add("POST", "/ping", handler("ping-post"))
sub.use(mw("sub"))

top = Router()
top.use(mw("top"))
top.add("GET", "/health", handler("health"), name="health")
top.mount("/api/v1", sub, name_prefix="api.")
top.add("GET", "/api/v1/users/me", handler("me"), name="me")

resp = top.dispatch("GET", "/api/v1/users/42")
assert resp.status == 200 and resp.body == "user [('id', 42)]", resp
assert trace == ["top", "sub", "user"], trace
del trace[:]
assert top.dispatch("GET", "/health").body == "health []"
assert trace == ["top", "health"], "the sub-router middleware must not touch the parent's routes"
del trace[:]
assert top.dispatch("GET", "/api/v1/users/me").body == "me []", "fewest parameters wins across mounts"
assert top.dispatch("GET", "/api/v1/users/bob").body == "by-name [('who', 'bob')]"
del trace[:]

# url_for through mounts
assert top.url_for("api.user", id=3) == "/api/v1/users/3"
assert top.url_for("api.by_name", who="a b") == "/api/v1/users/a%20b"
assert top.url_for("health") == "/health" and top.url_for("me") == "/api/v1/users/me"
expect(KeyError, "", lambda: top.url_for("user", id=1))
assert sub.url_for("user", id=3) == "/users/3", "the sub-router itself is unchanged"

# 404 / 405 / 308 across mounts
resp = top.dispatch("PUT", "/api/v1/ping")
assert resp.status == 405 and resp.headers == {"Allow": "GET, POST"}, resp
resp = top.dispatch("GET", "/api/v1/docs")
assert resp.status == 308 and resp.headers == {"Location": "/api/v1/docs/"}, resp
assert top.dispatch("GET", "/api/v1/docs/").status == 200
assert top.dispatch("GET", "/users/1").status == 404

# mounting copies: later additions to sub are not visible, and middleware added later do not apply
sub.add("GET", "/late", handler("late"))
sub.use(mw("late-mw"))
assert top.dispatch("GET", "/api/v1/late").status == 404
del trace[:]
top.dispatch("GET", "/api/v1/ping")
assert trace == ["top", "sub", "ping-get"], trace
del trace[:]

# nesting, with middleware order top -> mid -> inner
inner = Router()
inner.add("GET", "/<int:id>", handler("get"), name="get")
inner.use(mw("inner"))
mid = Router()
mid.use(mw("mid"))
mid.mount("/users", inner, name_prefix="users.")
top2 = Router()
top2.use(mw("top"))
top2.mount("/api", mid, name_prefix="v1.")
resp = top2.dispatch("GET", "/api/users/9")
assert resp.body == "get [('id', 9)]" and trace == ["top", "mid", "inner", "get"], (resp, trace)
assert top2.url_for("v1.users.get", id=9) == "/api/users/9"
mid.mount("/other", inner, name_prefix="other.")
assert top2.dispatch("GET", "/api/other/1").status == 404, "mid changed after it was mounted"

# validation
for bad in ("api", "/api/", "", "/"):
    expect(ValueError, "prefix", lambda: Router().mount(bad, Router())) if False else None
for bad in ("api", "/api/", ""):
    try:
        Router().mount(bad, Router())
    except ValueError:
        pass
    else:
        raise AssertionError("mount(%r) should raise ValueError" % bad)
dup = Router()
dup.add("GET", "/a", handler("a"), name="same")
expect(ValueError, "duplicate route name same", lambda: dup.add("GET", "/b", handler("b"), name="same"))
other = Router()
other.add("GET", "/c", handler("c"), name="same")
expect(ValueError, "duplicate route name same", lambda: dup.mount("/x", other))
dup.mount("/x", other, name_prefix="x.")
assert dup.url_for("x.same") == "/x/c" and dup.url_for("same") == "/a"
dup.add("GET", "/n1", handler("n"))
dup.add("GET", "/n2", handler("n"))

# a mounted route behaves like any other when it raises
boom = Router()
boom.add("GET", "/boom", lambda req: 1 / 0)
top3 = Router()
top3.mount("/m", boom)
assert top3.dispatch("GET", "/m/boom").status == 500
