def validate(jobs):
    """jobs: dict name -> Job. Raise ValueError('unknown dependency X of Y') for a dependency that does not exist and
    ValueError('cycle: a -> b -> a') (the cycle, closed) for any dependency cycle, including a job that depends on itself."""
    for job in jobs.values():
        for dep in job.deps:
            if dep not in jobs:
                raise ValueError("unknown dependency %s of %s" % (dep, job.name))

    seen = set()

    def visit(name, stack):
        if name in seen:
            return
        if name in stack:
            raise ValueError("cycle: " + " -> ".join(stack[stack.index(name):] + [name]))
        seen.add(name)
        for dep in jobs[name].deps:
            visit(dep, stack + [name])

    for name in jobs:
        visit(name, [])
