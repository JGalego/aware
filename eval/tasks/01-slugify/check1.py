from textutil import slugify
for arg, want in [("Hello, World!", "hello-world"), ("  A  b  ", "a-b"), ("---x---", "x"), ("", ""), ("100% sure", "100-sure"), ("a", "a")]:
    got = slugify(arg)
    assert got == want, "slugify(%r) -> %r, want %r" % (arg, got, want)
