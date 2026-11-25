import re

TOKEN = re.compile(r"\s*(\d+\.?\d*|[a-z]+|[-+*/^(),])")


def tokenize(src):
    pos, out = 0, []
    while pos < len(src):
        m = TOKEN.match(src, pos)
        if not m:
            if src[pos:].strip() == "":
                break
            raise ValueError("bad character at %d" % pos)
        out.append(m.group(1))
        pos = m.end()
    return out


def evaluate(src):
    """Evaluate + - * / ^ with the usual precedence, parentheses, unary minus and min(a, b) / max(a, b).

    Raises ValueError on malformed input and ZeroDivisionError on division by zero.
    """
    toks = tokenize(src)
    pos = 0

    def peek():
        return toks[pos] if pos < len(toks) else None

    def eat():
        nonlocal pos
        if pos >= len(toks):
            raise ValueError("unexpected end")
        t = toks[pos]
        pos += 1
        return t

    def expect(tok):
        if eat() != tok:
            raise ValueError("expected " + tok)

    def expr():
        v = term()
        while peek() in ("+", "-"):
            op = eat()
            r = term()
            v = v + r if op == "+" else v - r
        return v

    def term():
        v = unary()
        while peek() in ("*", "/"):
            op = eat()
            r = unary()
            v = v * r if op == "*" else v / r
        return v

    def unary():
        if peek() == "-":
            eat()
            return -unary()
        return power()

    def power():
        base = atom()
        if peek() == "^":
            eat()
            return base ** unary()
        return base

    def atom():
        t = eat()
        if t == "(":
            v = expr()
            expect(")")
            return v
        if t in ("min", "max"):
            expect("(")
            a = expr()
            expect(",")
            b = expr()
            expect(")")
            return min(a, b) if t == "min" else max(a, b)
        try:
            return float(t)
        except ValueError:
            raise ValueError("unexpected " + t)

    v = expr()
    if pos != len(toks):
        raise ValueError("trailing input")
    return v
