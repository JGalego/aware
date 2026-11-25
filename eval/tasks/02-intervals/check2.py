from intervals import total_covered, gaps, merge_intervals
assert merge_intervals([(1, 2), (2, 3)]) == [(1, 3)]
assert total_covered([(1, 3), (2, 5), (7, 8)]) == 5
assert total_covered([]) == 0
for args, want in [(([(2, 4), (6, 8)], 0, 10), [(0, 2), (4, 6), (8, 10)]), (([(0, 10)], 0, 10), []), (([], 1, 3), [(1, 3)]),
                   (([(-5, 2), (8, 20)], 0, 10), [(2, 8)]), (([(1, 2), (2, 3)], 0, 4), [(0, 1), (3, 4)]), (([(20, 30)], 0, 10), [(0, 10)])]:
    got = gaps(*args)
    assert got == want, "gaps%r -> %r, want %r" % (args, got, want)
