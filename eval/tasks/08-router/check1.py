from response import HTTPError, Response
from router import Router


def h(label):
    return lambda req, **p: "%s %s" % (label, sorted(p.items()))


def expect(exc, fn):
    try:
        fn()
    except exc:
        return
    raise AssertionError("expected %s" % exc.__name__)


# (1) literals are literal
r = Router()
r.add("GET", "/files/report.pdf", h("pdf"))
assert r.dispatch("GET", "/files/report.pdf").status == 200
assert r.dispatch("GET", "/files/reportXpdf").status == 404
r.add("GET", "/v1+2/x", h("plus"))
assert r.dispatch("GET", "/v1+2/x").status == 200 and r.dispatch("GET", "/v112/x").status == 404

# (2) fewest parameters wins, then registration order
r = Router()
r.add("GET", "/users/<id>", h("param"))
r.add("GET", "/users/me", h("me"))
assert r.dispatch("GET", "/users/me").body.startswith("me")
assert r.dispatch("GET", "/users/42").body == "param [('id', '42')]"
r = Router()
r.add("GET", "/a/<int:n>/<y>", h("two"))
r.add("GET", "/a/<x>/b", h("one"))
assert r.dispatch("GET", "/a/5/b").body.startswith("one")
r = Router()
r.add("GET", "/t/<a>", h("first"))
r.add("GET", "/t/<b>", h("second"))
assert r.dispatch("GET", "/t/z").body == "first [('a', 'z')]"
r = Router()
r.add("POST", "/m/<a>", h("post-param"))
r.add("GET", "/m/<a>", h("get-param"))
r.add("GET", "/m/fixed", h("get-fixed"))
assert r.dispatch("POST", "/m/fixed").body.startswith("post-param"), "a route for another method must not shadow"

# (3) 404, 405 and 308
r = Router()
r.add("GET", "/a", h("a"))
r.add("POST", "/a", h("a"))
r.add("GET", "/b", h("b"))
r.add("DELETE", "/b", h("b"))
r.add("GET", "/docs/", h("docs"))
resp = r.dispatch("PUT", "/a")
assert resp.status == 405 and resp.headers == {"Allow": "GET, POST"}, resp
resp = r.dispatch("PATCH", "/b")
assert resp.status == 405 and resp.headers["Allow"] == "DELETE, GET", resp
assert r.dispatch("get", "/a").status == 200
assert r.dispatch("GET", "/nope").status == 404
resp = r.dispatch("GET", "/docs")
assert resp.status == 308 and resp.headers == {"Location": "/docs/"}, resp
assert r.dispatch("GET", "/docs/").status == 200
assert r.dispatch("GET", "/a/").status == 404

# (4) url_for
r = Router()
r.add("GET", "/search/<q>", h("s"), name="s")
r.add("GET", "/f/<path:p>", h("f"), name="f")
r.add("GET", "/items/<int:id>/<slug>", h("i"), name="item")
assert r.url_for("s", q="a b/c") == "/search/a%20b%2Fc"
assert r.url_for("s", q="ünï") == "/search/%C3%BCn%C3%AF"
assert r.url_for("f", p="dir/a b.txt") == "/f/dir/a%20b.txt"
assert r.url_for("item", id=7, slug="x y") == "/items/7/x%20y"
assert r.url_for("item", id="12", slug="z") == "/items/12/z"
expect(ValueError, lambda: r.url_for("s"))
expect(ValueError, lambda: r.url_for("s", q="a", extra="b"))
expect(ValueError, lambda: r.url_for("item", id="abc", slug="x"))
expect(KeyError, lambda: r.url_for("nope"))

# (5) middleware order
trace = []

def mw(label):
    def run(req, nxt):
        trace.append(label + " in")
        resp = nxt(req)
        trace.append(label + " out %d" % resp.status)
        return resp
    return run

r = Router()
r.add("GET", "/x", lambda req: trace.append("handler") or "ok")
r.use(mw("m1"))
r.use(mw("m2"))
assert r.dispatch("GET", "/x").status == 200
assert trace == ["m1 in", "m2 in", "handler", "m2 out 200", "m1 out 200"], trace
del trace[:]
r.dispatch("GET", "/missing")
assert trace == [], "middleware do not run for unmatched requests"

# (6) errors
def gone(req, id):
    raise HTTPError(404, "no such user")

def broken(req):
    raise RuntimeError("bug")

r = Router()
r.add("GET", "/u/<id>", gone)
r.add("GET", "/broken", broken)
r.add("GET", "/resp", lambda req: Response(201, "made", {"X": "1"}))
del trace[:]
r.use(mw("m"))
resp = r.dispatch("GET", "/u/1")
assert (resp.status, resp.body) == (404, "no such user"), resp
resp = r.dispatch("GET", "/broken")
assert (resp.status, resp.body) == (500, "internal error"), resp
resp = r.dispatch("GET", "/resp")
assert (resp.status, resp.body, resp.headers) == (201, "made", {"X": "1"}), resp
assert trace == ["m in", "m out 404", "m in", "m out 500", "m in", "m out 201"], trace

# (7) int converter
r = Router()
seen = []
r.add("GET", "/items/<int:id>", lambda req, id: seen.append(id) or "ok")
assert r.dispatch("GET", "/items/5").status == 200 and seen == [5] and type(seen[0]) is int
assert r.dispatch("GET", "/items/05").status == 200 and seen == [5, 5]
for bad in ("/items/-5", "/items/+5", "/items/abc", "/items/5x", "/items/"):
    assert r.dispatch("GET", bad).status == 404, bad
