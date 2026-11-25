def merge_intervals(intervals):
    """Merge overlapping or touching (start, end) intervals; return a sorted list of tuples."""
    out = []
    for start, end in sorted(intervals):
        if out and start <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], end))
        else:
            out.append((start, end))
    return out
