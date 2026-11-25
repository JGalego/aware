import time


class TTLCache:
    """Small LRU cache whose entries expire ttl seconds after being stored.

    get() returns the value or None. A hit makes the key the most recently used one. An entry is expired
    once clock() reaches its expiry time. len() counts only live entries.
    """

    def __init__(self, capacity, ttl, clock=time.monotonic):
        self.capacity = capacity
        self.ttl = ttl
        self.clock = clock
        self.data = {}  # key -> (value, expires_at); dict order is recency order, oldest first

    def put(self, key, value):
        if key in self.data:
            del self.data[key]
        self.data[key] = (value, self.clock() + self.ttl)
        while len(self.data) > self.capacity:
            del self.data[next(iter(self.data))]

    def get(self, key):
        item = self.data.get(key)
        if item is None:
            return None
        value, expires = item
        if self.clock() > expires:
            del self.data[key]
            return None
        return value

    def __len__(self):
        return len(self.data)
