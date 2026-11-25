def low_stock(state, threshold):
    """Items whose available quantity is at or below threshold, as (item, available) sorted by available, then item."""
    rows = [(item, state.available(item)) for item in state.on_hand if state.available(item) <= threshold]
    return sorted(rows, key=lambda r: (r[1], r[0]))
