from projections import Stock


def take(state):
    """A plain-dict copy of the state that later changes to the state cannot touch."""
    return {
        "on_hand": dict(state.on_hand),
        "reservations": {order: dict(held) for order, held in state.reservations.items()},
        "last_seq": state.last_seq,
    }


def restore(snap):
    state = Stock()
    state.on_hand = dict(snap["on_hand"])
    state.reservations = {order: dict(held) for order, held in snap["reservations"].items()}
    state.last_seq = snap["last_seq"]
    return state


def rebuild(store, snap=None):
    """State after replaying the store, starting from a snapshot if one is given."""
    state = restore(snap) if snap else Stock()
    for ev in store.events(after_seq=state.last_seq):
        state.apply(ev)
    return state
