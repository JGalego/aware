from response import HTTPError, Response
from route import Route


class Request:
    def __init__(self, method, path, params):
        self.method = method
        self.path = path
        self.params = params
        self.ctx = {}


class Router:
    """Dispatches (method, path) to handlers.

    Handlers are called as handler(request, **params) and return a str body or a Response. When several routes match, the one with
    the fewest parameters wins, then the first registered. No path match is a 404; a path that matches only for other methods is a
    405 whose Allow header lists the methods that path does accept, sorted, joined with ', '; a path that is missing its trailing
    slash (only '/docs/' is registered, '/docs' was asked for) is a 308 with Location set to the slash version. A handler may raise
    HTTPError(status, message) to answer with that status; any other exception is a 500 'internal error'. Middleware are
    functions mw(request, next) -> Response; the first one registered is the outermost, and they run only for matched routes.
    """

    def __init__(self):
        self.routes = []
        self.middleware = []

    def _check_name(self, name):
        if name is not None and any(r.name == name for r in self.routes):
            raise ValueError("duplicate route name " + name)

    def add(self, method, pattern, handler, name=None):
        self._check_name(name)
        self.routes.append(Route(method, pattern, handler, name))

    def use(self, fn):
        self.middleware.append(fn)

    def mount(self, prefix, sub, name_prefix=""):
        if not prefix.startswith("/") or prefix.endswith("/"):
            raise ValueError("prefix must start with / and must not end with /")
        copies = []
        for r in sub.routes:
            name = name_prefix + r.name if r.name else None
            copy = Route(r.method, prefix + r.pattern, r.handler, name)
            copy.middleware = list(sub.middleware) + list(r.middleware)
            copies.append(copy)
        names = [c.name for c in copies if c.name]
        for n in names:
            self._check_name(n)
        if len(set(names)) != len(names):
            raise ValueError("duplicate route name " + sorted(n for n in names if names.count(n) > 1)[0])
        self.routes.extend(copies)

    def url_for(self, name, **values):
        for route in self.routes:
            if route.name == name:
                return route.build(**values)
        raise KeyError(name)

    def dispatch(self, method, path):
        method = method.upper()
        found = [(r, p) for r in self.routes for p in [r.match(path)] if p is not None]
        usable = sorted(((r, p) for r, p in found if r.method == method), key=lambda rp: len(rp[1]))
        if not usable:
            if found:
                allow = sorted({r.method for r, _ in found})
                return Response(405, "method not allowed", {"Allow": ", ".join(allow)})
            if not path.endswith("/") and any(r.match(path + "/") is not None for r in self.routes):
                return Response(308, "", {"Location": path + "/"})
            return Response(404, "not found")
        route, params = usable[0]
        request = Request(method, path, params)

        def endpoint(req):
            try:
                out = route.handler(req, **req.params)
            except HTTPError as exc:
                return Response(exc.status, exc.message)
            except Exception:
                return Response(500, "internal error")
            return out if isinstance(out, Response) else Response(200, out)

        chain = endpoint
        for mw in reversed(self.middleware + route.middleware):
            chain = (lambda mw, nxt: lambda req: mw(req, nxt))(mw, chain)
        return chain(request)
