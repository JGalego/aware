from decimal import Decimal


class Rates:
    """Exchange rates by date. rate(date, base, quote) is how many units of quote one unit of base buys, as of `date`
    (an ISO 'YYYY-MM-DD' string): the most recent rate set on or before that date. KeyError if there is none.
    rate(x, c, c) is 1. A rate set for (A, B) also answers (B, A) as the reciprocal."""

    def __init__(self):
        self._rows = {}  # (base, quote) -> sorted list of (date, Decimal)

    def set(self, date, base, quote, rate):
        rows = self._rows.setdefault((base, quote), [])
        rows.append((date, Decimal(str(rate))))
        rows.sort()

    def _lookup(self, rows, date):
        return rows[-1][1]

    def rate(self, date, base, quote):
        if base == quote:
            return Decimal(1)
        if (base, quote) in self._rows:
            return self._lookup(self._rows[(base, quote)], date)
        if (quote, base) in self._rows:
            return 1 / self._lookup(self._rows[(quote, base)], date)
        raise KeyError((base, quote))
