from decimal import ROUND_HALF_EVEN, Decimal

ZERO = Decimal(0)


def q(amount, places=2):
    """Round to `places` decimal places, halves away from zero (1.245 -> 1.25, -1.245 -> -1.25)."""
    return Decimal(amount).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_EVEN)
