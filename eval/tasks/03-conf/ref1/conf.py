def parse(text):
    """Parse 'key = value' lines into a dict of str -> str. '#' starts a comment, on its own line or after a value."""
    out = {}
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        key, _, value = line.partition("=")
        out[key.strip()] = value.strip()
    return out
