import snapshot
from api import Inventory, OutOfStock
from events import RESERVED
from projections import Stock
from report import low_stock
from store import EventStore


class Clock:
    t = 0

    def __call__(self):
        return self.t


def new():
    s = EventStore()
    return Inventory(s, Clock()), s


# (1) the last unit can be reserved
inv, _ = new()
inv.stock("a", 5)
inv.reserve("o1", "a", 5)
assert inv.available("a") == 0
for item_qty in (("a", 1), ("b", 1)):
    try:
        inv.reserve("o2", *item_qty)
    except OutOfStock:
        pass
    else:
        raise AssertionError("reserving %r should fail" % (item_qty,))
inv2, _ = new()
inv2.stock("a", 5)
try:
    inv2.reserve("o1", "a", 6)
except OutOfStock:
    pass
else:
    raise AssertionError("6 of 5 should fail")

# (2) shipping consumes the reservation
inv, _ = new()
inv.stock("a", 10)
inv.reserve("o1", "a", 4)
inv.ship("o1")
assert inv.state.on_hand["a"] == 6, inv.state.on_hand
assert inv.available("a") == 6, inv.available("a")
assert inv.state.reservations == {}, inv.state.reservations

# (3) the same item twice adds up
inv, _ = new()
inv.stock("a", 10)
inv.reserve("o1", "a", 3)
inv.reserve("o1", "a", 4)
assert inv.available("a") == 3, inv.available("a")
inv.ship("o1")
assert inv.state.on_hand["a"] == 3

# (4) shipping something that is not reserved
inv, store = new()
inv.stock("a", 10)
n = len(store)
for bad in ("nope",):
    try:
        inv.ship(bad)
    except KeyError:
        pass
    else:
        raise AssertionError("ship of unknown order should raise KeyError")
assert len(store) == n, "a refused ship must not be logged"
inv.reserve("o1", "a", 1)
inv.ship("o1")
try:
    inv.ship("o1")
except KeyError:
    pass
else:
    raise AssertionError("second ship should raise KeyError")

# (5) low_stock
inv, _ = new()
inv.stock("a", 5)
inv.stock("b", 2)
inv.stock("c", 10)
inv.stock("d", 4)
inv.reserve("o1", "b", 2)
got = low_stock(inv.state, 4)
assert got == [("b", 0), ("d", 4)], got
assert low_stock(inv.state, 5) == [("b", 0), ("d", 4), ("a", 5)], low_stock(inv.state, 5)
assert low_stock(inv.state, -1) == []

# (6) snapshots are independent copies
inv, store = new()
inv.stock("a", 10)
inv.reserve("o1", "a", 3)
snap = snapshot.take(inv.state)
inv.reserve("o1", "a", 2)
inv.stock("a", 1)
first = snapshot.rebuild(store, snap)
again = snapshot.rebuild(store, snap)
full = snapshot.rebuild(store)
assert first.on_hand == again.on_hand == full.on_hand, (first.on_hand, again.on_hand, full.on_hand)
assert first.reservations == again.reservations == full.reservations == {"o1": {"a": 5}}, (first.reservations, again.reservations)
assert snap["reservations"] == {"o1": {"a": 3}}, snap["reservations"]
s = snapshot.restore(snap)
s.apply({"type": RESERVED, "seq": 99, "ts": 0, "order": "o1", "item": "a", "qty": 1})
assert snap["reservations"] == {"o1": {"a": 3}}, "restore must not share inner dicts with the snapshot"
