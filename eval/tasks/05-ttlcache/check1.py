from cache import TTLCache


class Clock:
    t = 0

    def __call__(self):
        return self.t


c = Clock()
k = TTLCache(2, 10, clock=c)
k.put("a", 1)
k.put("b", 2)
assert k.get("a") == 1
k.put("c", 3)
assert k.get("b") is None, "b should have been evicted, not a"
assert k.get("a") == 1 and k.get("c") == 3

c = Clock()
k = TTLCache(5, 10, clock=c)
k.put("x", 1)
c.t = 9.99
assert k.get("x") == 1
c.t = 10
assert k.get("x") is None, "expired at exactly ttl"

c = Clock()
k = TTLCache(5, 10, clock=c)
k.put("a", 1)
k.put("b", 2)
c.t = 5
k.put("c", 3)
assert len(k) == 3
c.t = 10
assert len(k) == 1, len(k)
c.t = 15
assert len(k) == 0
