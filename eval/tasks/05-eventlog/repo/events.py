"""Event types for the inventory log.

An event is a plain dict with a 'type', a 'seq' (1, 2, 3, ... in append order) and a 'ts' (the clock reading when it was written),
plus the fields listed next to each type.
"""

STOCKED = "stocked"      # item, qty            on_hand[item] += qty
RESERVED = "reserved"    # order, item, qty     the order holds qty more units of item
RELEASED = "released"    # order                the order gives back everything it holds
SHIPPED = "shipped"      # order                the order's held units leave on_hand; the reservation is consumed
ADJUSTED = "adjusted"    # item, delta          on_hand[item] += delta (delta may be negative: shrinkage)


def make(type_, seq, ts, **fields):
    ev = {"type": type_, "seq": seq, "ts": ts}
    ev.update(fields)
    return ev
