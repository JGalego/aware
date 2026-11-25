from intervals import merge_intervals as m
for arg, want in [([(1, 2), (2, 3)], [(1, 3)]), ([(5, 6), (1, 2), (2, 4)], [(1, 4), (5, 6)]), ([(1, 10), (2, 3)], [(1, 10)]), ([], []), ([(1, 2), (3, 4)], [(1, 2), (3, 4)]), ([(3, 4), (1, 3), (4, 6)], [(1, 6)])]:
    got = m(arg)
    assert got == want, "merge_intervals(%r) -> %r, want %r" % (arg, got, want)
