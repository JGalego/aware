from cache import TTLCache


class Clock:
    t = 0

    def __call__(self):
        return self.t


c = Clock()
k = TTLCache(5, 10, clock=c)
k.put("a", 1)
c.t = 5
k.put("b", 2)
c.t = 12
assert k.purge() == 1
assert len(k) == 1 and k.get("b") == 2
assert k.purge() == 0

calls = []
def make():
    calls.append(1)
    return "v"
assert k.get_or_put("n", make) == "v" and len(calls) == 1
assert k.get_or_put("n", make) == "v" and len(calls) == 1, "factory must not run on a hit"
c.t = 100
assert k.get_or_put("n", make) == "v" and len(calls) == 2, "expired entry is a miss"
k2 = TTLCache(1, 10, clock=c)
k2.put("a", 1)
k2.get_or_put("b", lambda: 2)
assert k2.get("a") is None and k2.get("b") == 2
