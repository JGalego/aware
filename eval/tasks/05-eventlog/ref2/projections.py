from events import ADJUSTED, RELEASED, RESERVED, SHIPPED, STOCKED


class Stock:
    """The current state, built by applying events in order.

    on_hand[item] is the physical count; reservations[order] is {item: qty} held for that order;
    expiry[order] is when that reservation lapses; available(item) is on_hand minus everything reserved for it.
    """

    def __init__(self):
        self.on_hand = {}
        self.reservations = {}
        self.expiry = {}
        self.last_seq = 0

    def active(self, order, now=None):
        return now is None or self.expiry.get(order, float("inf")) > now

    def reserved(self, item, now=None):
        return sum(r.get(item, 0) for order, r in self.reservations.items() if self.active(order, now))

    def available(self, item, now=None):
        return self.on_hand.get(item, 0) - self.reserved(item, now)

    def apply(self, ev):
        t = ev["type"]
        if t == STOCKED:
            self.on_hand[ev["item"]] = self.on_hand.get(ev["item"], 0) + ev["qty"]
        elif t == RESERVED:
            held = self.reservations.setdefault(ev["order"], {})
            held[ev["item"]] = held.get(ev["item"], 0) + ev["qty"]
            if ev.get("expires_at") is not None:
                self.expiry[ev["order"]] = max(self.expiry.get(ev["order"], ev["expires_at"]), ev["expires_at"])
        elif t == RELEASED:
            self.reservations.pop(ev["order"], None)
            self.expiry.pop(ev["order"], None)
        elif t == SHIPPED:
            for item, qty in self.reservations.pop(ev["order"], {}).items():
                self.on_hand[item] -= qty
            self.expiry.pop(ev["order"], None)
        elif t == ADJUSTED:
            self.on_hand[ev["item"]] = self.on_hand.get(ev["item"], 0) + ev["delta"]
        self.last_seq = ev["seq"]
