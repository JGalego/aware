from events import ADJUSTED, RELEASED, RESERVED, SHIPPED, STOCKED


class Stock:
    """The current state, built by applying events in order.

    on_hand[item] is the physical count; reservations[order] is {item: qty} held for that order;
    available(item) is on_hand minus everything reserved for it.
    """

    def __init__(self):
        self.on_hand = {}
        self.reservations = {}
        self.last_seq = 0

    def reserved(self, item):
        return sum(r.get(item, 0) for r in self.reservations.values())

    def available(self, item):
        return self.on_hand.get(item, 0) - self.reserved(item)

    def apply(self, ev):
        t = ev["type"]
        if t == STOCKED:
            self.on_hand[ev["item"]] = self.on_hand.get(ev["item"], 0) + ev["qty"]
        elif t == RESERVED:
            held = self.reservations.setdefault(ev["order"], {})
            held[ev["item"]] = held.get(ev["item"], 0) + ev["qty"]
        elif t == RELEASED:
            self.reservations.pop(ev["order"], None)
        elif t == SHIPPED:
            for item, qty in self.reservations.pop(ev["order"], {}).items():
                self.on_hand[item] -= qty
        elif t == ADJUSTED:
            self.on_hand[ev["item"]] = self.on_hand.get(ev["item"], 0) + ev["delta"]
        self.last_seq = ev["seq"]
