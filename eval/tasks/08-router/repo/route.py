import re
from urllib.parse import quote

from converters import CONVERTERS, PARAM


class Route:
    """One method + URL pattern + handler. Patterns look like /users/<int:id>/posts/<slug>; <name> means <str:name>.

    match(path) returns {name: converted value} or None. build(**values) is the reverse: it fills the pattern in, percent-encoding
    str values completely and path values except for '/', and checks that the values given are exactly the parameters expected.
    """

    def __init__(self, method, pattern, handler, name=None):
        self.method = method.upper()
        self.pattern = pattern
        self.handler = handler
        self.name = name
        self.params = []
        regex, pos = "", 0
        for m in PARAM.finditer(pattern):
            regex += pattern[pos:m.start()]
            conv = m.group(1) or "str"
            if conv not in CONVERTERS:
                raise ValueError("unknown converter " + conv)
            regex += "(?P<%s>%s)" % (m.group(2), CONVERTERS[conv][0])
            self.params.append((m.group(2), conv))
            pos = m.end()
        regex += pattern[pos:]
        self.regex = re.compile("^" + regex + "$")

    def match(self, path):
        m = self.regex.match(path)
        if m is None:
            return None
        return {name: CONVERTERS[conv][1](m.group(name)) for name, conv in self.params}

    def build(self, **values):
        expected = {name for name, _ in self.params}
        if set(values) != expected:
            raise ValueError("expected parameters %s" % sorted(expected))

        def fill(m):
            conv, value = m.group(1) or "str", values[m.group(2)]
            if conv == "int":
                return str(int(value))
            return str(value)

        return PARAM.sub(fill, self.pattern)
