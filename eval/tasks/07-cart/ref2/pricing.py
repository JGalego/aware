def line_total(price, qty, discount_pct=0):
    """Price is integer cents. Return the line total in cents after a percentage discount, rounded half up."""
    return (price * qty * (100 - discount_pct) + 50) // 100
