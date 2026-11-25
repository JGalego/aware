VALUES = [(1000, "M"), (500, "D"), (100, "C"), (50, "L"), (10, "X"), (5, "V"), (1, "I")]


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
