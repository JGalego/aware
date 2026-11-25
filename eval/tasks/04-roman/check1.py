from roman import to_roman
for n, want in [(1, "I"), (4, "IV"), (9, "IX"), (14, "XIV"), (40, "XL"), (90, "XC"), (400, "CD"), (900, "CM"), (1994, "MCMXCIV"), (3999, "MMMCMXCIX"), (2024, "MMXXIV")]:
    assert to_roman(n) == want, (n, to_roman(n), want)
for bad in (0, 4000, -1):
    try:
        to_roman(bad)
    except ValueError:
        continue
    raise AssertionError("no ValueError for %r" % bad)
