from events import ADJUSTED, RELEASED, RESERVED, SHIPPED, STOCKED
from projections import Stock


class OutOfStock(Exception):
    pass


class Inventory:
    """Commands. Each validates against the current state, appends one event and applies it."""

    def __init__(self, store, clock, default_ttl=900):
        self.store = store
        self.clock = clock
        self.default_ttl = default_ttl
        self.state = Stock()

    def _emit(self, type_, ts=None, **fields):
        ev = self.store.append(type_, self.clock() if ts is None else ts, **fields)
        self.state.apply(ev)
        return ev

    def available(self, item):
        return self.state.available(item, self.clock())

    def stock(self, item, qty):
        if qty <= 0:
            raise ValueError("qty must be positive")
        return self._emit(STOCKED, item=item, qty=qty)

    def adjust(self, item, delta):
        return self._emit(ADJUSTED, item=item, delta=delta)

    def reserve(self, order, item, qty, ttl=None):
        if qty <= 0:
            raise ValueError("qty must be positive")
        now = self.clock()
        if self.state.available(item, now) < qty:
            raise OutOfStock(item)
        ttl = self.default_ttl if ttl is None else ttl
        return self._emit(RESERVED, ts=now, order=order, item=item, qty=qty, expires_at=now + ttl)

    def release(self, order):
        if order not in self.state.reservations:
            raise KeyError(order)
        return self._emit(RELEASED, order=order)

    def ship(self, order):
        if order not in self.state.reservations or not self.state.active(order, self.clock()):
            raise KeyError(order)
        return self._emit(SHIPPED, order=order)

    def sweep(self):
        now = self.clock()
        lapsed = sorted(o for o in self.state.reservations if not self.state.active(o, now))
        for order in lapsed:
            self._emit(RELEASED, ts=now, order=order, reason="expired")
        return lapsed
