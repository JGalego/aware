from conf import parse
got = parse("a = 1 # one\nb=two\n# c = 3\n\nd = x#y\ne =\n")
assert got == {"a": "1", "b": "two", "d": "x", "e": ""}, got
assert parse("") == {}
