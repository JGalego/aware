VALUES = [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"), (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]
SINGLE = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}


def to_roman(n):
    """Convert 1..3999 to a Roman numeral in standard subtractive notation (4 is IV, 9 is IX, 40 is XL, 90 is XC, 400 is CD, 900 is CM)."""
    if not 1 <= n <= 3999:
        raise ValueError(n)
    out = ""
    for value, sym in VALUES:
        while n >= value:
            out += sym
            n -= value
    return out


def from_roman(s):
    s = s.upper()
    if not s or any(c not in SINGLE for c in s):
        raise ValueError(s)
    total = 0
    for i, c in enumerate(s):
        v = SINGLE[c]
        total += -v if i + 1 < len(s) and SINGLE[s[i + 1]] > v else v
    if not 1 <= total <= 3999 or to_roman(total) != s:
        raise ValueError(s)
    return total
