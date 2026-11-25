from textutil import slugify
for args, want in [(("hello big world", 9), "hello-big"), (("hello big world", 8), "hello"), (("hello big world", 3), "hel"),
                   (("hello big world", 11), "hello-big"), (("hello big world", 10), "hello-big"), (("hello big world", 15), "hello-big-world"),
                   (("hello big world", 99), "hello-big-world"), (("Hello, World!", 5), "hello")]:
    got = slugify(*args)
    assert got == want, "slugify%r -> %r, want %r" % (args, got, want)
assert slugify("Hello, World!") == "hello-world"
