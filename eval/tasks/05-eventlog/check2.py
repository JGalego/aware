import snapshot
from api import Inventory, OutOfStock
from projections import Stock
from store import EventStore


class Clock:
    t = 0

    def __call__(self):
        return self.t


def new(ttl=100):
    s, c = EventStore(), Clock()
    return Inventory(s, c, default_ttl=ttl), s, c


def same(a, b):
    assert a.on_hand == b.on_hand, (a.on_hand, b.on_hand)
    assert a.reservations == b.reservations, (a.reservations, b.reservations)
    assert a.expiry == b.expiry, (a.expiry, b.expiry)
    assert a.last_seq == b.last_seq


inv, store, c = new()
inv.stock("a", 10)
c.t = 0
ev = inv.reserve("o1", "a", 4)
assert ev["expires_at"] == 100 and ev["ts"] == 0, ev
assert inv.available("a") == 6
c.t = 99
assert inv.available("a") == 6
c.t = 100
assert inv.available("a") == 10, "lapsed at exactly expires_at"
assert inv.state.available("a") == 6 and inv.state.available("a", now=50) == 6 and inv.state.available("a", now=100) == 10
assert inv.state.reserved("a") == 4 and inv.state.reserved("a", 100) == 0
try:
    inv.ship("o1")
except KeyError:
    pass
else:
    raise AssertionError("ship of a lapsed order should raise KeyError")
assert "o1" in inv.state.reservations, "not swept yet"
n = len(store)
assert inv.sweep() == ["o1"]
assert len(store) == n + 1 and store.events()[-1]["type"] == "released" and store.events()[-1]["reason"] == "expired"
assert "o1" not in inv.state.reservations and "o1" not in inv.state.expiry
assert inv.sweep() == [] and len(store) == n + 1

# custom ttl, and the latest expiry wins when an order reserves again
inv, store, c = new()
inv.stock("a", 10)
inv.stock("b", 10)
c.t = 100
inv.reserve("o2", "a", 3, ttl=10)
assert inv.state.expiry["o2"] == 110
c.t = 105
assert inv.available("a") == 7
inv.reserve("o2", "b", 2, ttl=50)
assert inv.state.expiry["o2"] == 155
c.t = 120
assert inv.available("a") == 7 and inv.available("b") == 8, "the order lives until its latest expiry"
c.t = 154
assert inv.available("a") == 7 and inv.available("b") == 8
c.t = 155
assert inv.available("a") == 10 and inv.available("b") == 10 and inv.state.reserved("a") == 3

# a lapsed reservation does not block a new one, and sweep orders by order id
inv, store, c = new(ttl=5)
inv.stock("a", 10)
c.t = 200
inv.reserve("z9", "a", 6)
inv.reserve("a1", "a", 4)
c.t = 205
inv.reserve("o4", "a", 10)
assert inv.sweep() == ["a1", "z9"]
assert sorted(inv.state.reservations) == ["o4"]
inv.ship("o4")
assert inv.state.on_hand["a"] == 0
try:
    inv.reserve("o5", "a", 1)
except OutOfStock:
    pass
else:
    raise AssertionError("nothing left")

# still active orders ship normally
inv, store, c = new()
inv.stock("a", 10)
inv.reserve("o1", "a", 4)
c.t = 50
inv.ship("o1")
assert inv.state.on_hand["a"] == 6 and inv.available("a") == 6

# replay and snapshots agree, expiry included
inv, store, c = new(ttl=100)
inv.stock("a", 10)
c.t = 10
inv.reserve("o1", "a", 2)
c.t = 20
inv.reserve("o2", "a", 3, ttl=500)
snap = snapshot.take(inv.state)
assert snap["expiry"] == {"o1": 110, "o2": 520}, snap
c.t = 30
inv.reserve("o1", "a", 1, ttl=200)
c.t = 700
inv.sweep()
inv.stock("a", 5)
full = snapshot.rebuild(store)
same(full, inv.state)
mid = snapshot.rebuild(store, snap)
same(mid, full)
snap2 = snapshot.take(snapshot.restore(snap))
assert snap2 == snap
mid.apply({"type": "reserved", "seq": 999, "ts": 0, "order": "o2", "item": "a", "qty": 1, "expires_at": 9999})
assert snap["expiry"] == {"o1": 110, "o2": 520} and snap["reservations"]["o2"] == {"a": 3}, "snapshot must stay untouched"

# events from before expiry existed never lapse
st = Stock()
st.apply({"type": "stocked", "seq": 1, "ts": 0, "item": "a", "qty": 5})
st.apply({"type": "reserved", "seq": 2, "ts": 0, "order": "old", "item": "a", "qty": 2})
assert st.available("a", now=10 ** 9) == 3
