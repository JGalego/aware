PENDING, DONE, FAILED, SKIPPED, CANCELLED = "pending", "done", "failed", "skipped", "cancelled"


class Job:
    """A unit of work. run() takes no arguments, returns None (or how long it took) and raises on failure.

    deps are the names of jobs that must be DONE first; a higher priority runs first; a failed attempt is retried up to `retries`
    times, waiting backoff * 2**(n-1) seconds after the n-th failure.
    """

    def __init__(self, name, run, deps=(), priority=0, retries=0, backoff=1.0, timeout=None):
        self.name = name
        self.run = run
        self.deps = list(deps)
        self.priority = priority
        self.retries = retries
        self.backoff = backoff
        self.timeout = timeout
        self.state = PENDING
        self.attempts = 0
        self.not_before = 0.0
        self.error = None
