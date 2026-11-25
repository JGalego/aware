from conf import parse
got = parse("top=1\n[db]\nhost = h # x\nport=5\n[cache] # c\nttl = 9\n")
assert got == {"top": "1", "db.host": "h", "db.port": "5", "cache.ttl": "9"}, got
assert parse("a = 1 # one") == {"a": "1"}
