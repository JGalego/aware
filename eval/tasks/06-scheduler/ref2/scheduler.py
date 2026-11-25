from graph import validate
from job import CANCELLED, DONE, FAILED, PENDING, SKIPPED


class _Timeout(Exception):
    pass


class Scheduler:
    """Runs jobs respecting dependencies, priorities, a per-tick limit and retries with backoff.

    Time is passed in, so runs are deterministic. tick(now) starts at most max_parallel ready jobs (highest priority first, ties by
    name) and returns how many it started. log collects (now, name, 'ok' | 'fail') for every attempt; done_order lists the jobs
    that succeeded, in order. A job whose dependency failed or was skipped is skipped, all the way down.
    """

    def __init__(self, jobs, max_parallel=1):
        self.jobs = {j.name: j for j in jobs}
        validate(self.jobs)
        self.max_parallel = max_parallel
        self.log = []
        self.done_order = []

    def ready(self, now):
        out = [
            j for j in self.jobs.values()
            if j.state == PENDING and now >= j.not_before and all(self.jobs[d].state == DONE for d in j.deps)
        ]
        return sorted(out, key=lambda j: (-j.priority, j.name))

    def tick(self, now):
        started = 0
        for job in self.ready(now)[: self.max_parallel]:
            started += 1
            try:
                took = job.run()
                if job.timeout is not None and (took or 0) > job.timeout:
                    raise _Timeout("timeout")
            except Exception as exc:
                job.attempts += 1
                self.log.append((now, job.name, "fail"))
                if job.attempts <= job.retries:
                    job.not_before = now + job.backoff * 2 ** (job.attempts - 1)
                else:
                    job.state = FAILED
                    job.error = "timeout" if isinstance(exc, _Timeout) else str(exc)
            else:
                job.state = DONE
                self.done_order.append(job.name)
                self.log.append((now, job.name, "ok"))
        self._skip_dependents()
        return started

    def _skip_dependents(self):
        changed = True
        while changed:
            changed = False
            for job in self.jobs.values():
                if job.state == PENDING and any(self.jobs[d].state in (FAILED, SKIPPED) for d in job.deps):
                    job.state = SKIPPED
                    changed = True

    def run_all(self, start=0.0, step=1.0, max_ticks=1000):
        """Tick until nothing is pending (or max_ticks). Returns the final time."""
        now = start
        for _ in range(max_ticks):
            if not any(j.state == PENDING for j in self.jobs.values()):
                break
            self.tick(now)
            now += step
        return now

    def cancel(self, name):
        job = self.jobs[name]
        if job.state == CANCELLED:
            return
        if job.state != PENDING:
            raise ValueError("cannot cancel %s job" % job.state)
        job.state = CANCELLED
        changed = True
        while changed:
            changed = False
            for other in self.jobs.values():
                if other.state == PENDING and any(self.jobs[d].state == CANCELLED for d in other.deps):
                    other.state = CANCELLED
                    changed = True
