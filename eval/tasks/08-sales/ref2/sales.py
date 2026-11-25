import csv
import io
from collections import defaultdict


def monthly_totals(csv_text):
    """csv columns: date (YYYY-MM-DD) and amount (decimal string; blank counts as 0).

    Return a dict 'YYYY-MM' -> total rounded to 2 places, with the months in chronological order.
    """
    totals = defaultdict(float)
    for row in csv.DictReader(io.StringIO(csv_text)):
        totals[row["date"][:7]] += float(row["amount"] or 0)
    return {k: round(totals[k], 2) for k in sorted(totals)}


def with_change(totals):
    out, prev = [], None
    for month, total in totals.items():
        pct = None if prev in (None, 0) else round((total - prev) / prev * 100, 1)
        out.append((month, total, pct))
        prev = total
    return out


def best_months(csv_text, n=3):
    totals = monthly_totals(csv_text)
    return sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))[:n]
