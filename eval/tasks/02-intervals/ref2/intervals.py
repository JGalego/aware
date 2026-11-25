def merge_intervals(intervals):
    """Merge overlapping or touching (start, end) intervals; return a sorted list of tuples."""
    out = []
    for start, end in sorted(intervals):
        if out and start <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], end))
        else:
            out.append((start, end))
    return out


def total_covered(intervals):
    return sum(e - s for s, e in merge_intervals(intervals))


def gaps(intervals, lo, hi):
    out, pos = [], lo
    for s, e in merge_intervals(intervals):
        if e <= lo:
            continue
        if s >= hi:
            break
        if s > pos:
            out.append((pos, s))
        pos = max(pos, e)
    if pos < hi:
        out.append((pos, hi))
    return out
