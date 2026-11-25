from events import make


class EventStore:
    """Append-only log. append() assigns seq numbers 1, 2, 3, ...; events(after_seq) returns the later ones, in order."""

    def __init__(self):
        self._events = []

    def append(self, type_, ts, **fields):
        ev = make(type_, len(self._events) + 1, ts, **fields)
        self._events.append(ev)
        return ev

    def events(self, after_seq=0):
        return [e for e in self._events if e["seq"] > after_seq]

    def __len__(self):
        return len(self._events)
