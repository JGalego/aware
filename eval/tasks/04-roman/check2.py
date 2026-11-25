from roman import to_roman, from_roman
assert from_roman("MCMXCIV") == 1994 and from_roman("iv") == 4 and from_roman("MMMCMXCIX") == 3999
for n in range(1, 4000):
    assert from_roman(to_roman(n)) == n, n
for bad in ("IIII", "VX", "IC", "", "ABC", "MMMM", "IIX", "XM", "VV"):
    try:
        from_roman(bad)
    except ValueError:
        continue
    raise AssertionError("no ValueError for %r" % bad)
