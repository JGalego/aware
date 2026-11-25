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

    def _emit(self, type_, **fields):
        ev = self.store.append(type_, self.clock(), **fields)
        self.state.apply(ev)
        return ev

    def available(self, item):
        return self.state.available(item)

    def stock(self, item, qty):
        if qty <= 0:
            raise ValueError("qty must be positive")
        return self._emit(STOCKED, item=item, qty=qty)

    def adjust(self, item, delta):
        return self._emit(ADJUSTED, item=item, delta=delta)

    def reserve(self, order, item, qty):
        if qty <= 0:
            raise ValueError("qty must be positive")
        if self.state.available(item) <= qty:
            raise OutOfStock(item)
        return self._emit(RESERVED, order=order, item=item, qty=qty)

    def release(self, order):
        if order not in self.state.reservations:
            raise KeyError(order)
        return self._emit(RELEASED, order=order)

    def ship(self, order):
        return self._emit(SHIPPED, order=order)
