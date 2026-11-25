from money import ZERO, q


def trial_balance(ledger, as_of):
    """[(name, debit, credit)] sorted by name, every balance converted to the base currency at the rate in force on as_of
    and rounded to 2 places. A net debit goes in the debit column, a net credit in the credit column."""
    rows = []
    for name in sorted(ledger.accounts):
        acct = ledger.accounts[name]
        bal = ledger.balance(name, as_of)
        base = q(bal * ledger.rates.rate(as_of, acct.currency, ledger.base))
        debit, credit = (base, ZERO) if base >= 0 else (ZERO, -base)
        rows.append((name, debit, credit))
    return rows
