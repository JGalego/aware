from job import DONE, FAILED, PENDING, SKIPPED


def summary(sched):
    """Counts per state plus 'order', the names of the jobs that succeeded, in the order they did."""
    counts = {s: 0 for s in (DONE, FAILED, SKIPPED, PENDING)}
    for job in sched.jobs.values():
        counts[job.state] += 1
    counts["order"] = list(sched.done_order)
    return counts
