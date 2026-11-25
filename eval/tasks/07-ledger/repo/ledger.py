from decimal import Decimal

from accounts import Account
from money import ZERO, q


class Ledger:
    """Double-entry books in several currencies.

    A transaction is a date, a memo and lines (account name, amount): the amount is in the account's own currency, positive for a
    debit and negative for a credit. It balances when its lines, each converted to the base currency at the transaction date and
    rounded to 2 places, add up to exactly zero.
    """

    def __init__(self, base, rates):
        self.base = base
        self.rates = rates
        self.accounts = {}
        self.transactions = []

    def open(self, name, kind, currency=None):
        if name in self.accounts:
            raise ValueError("duplicate account " + name)
        self.accounts[name] = Account(name, kind, currency or self.base)
        return self.accounts[name]

    def to_base(self, amount, currency, date):
        return q(Decimal(str(amount)) * self.rates.rate(date, currency, self.base))

    def post(self, date, memo, lines):
        if len(lines) < 2:
            raise ValueError("a transaction needs at least two lines")
        parsed = []
        for name, amount in lines:
            if name not in self.accounts:
                raise KeyError(name)
            parsed.append((name, Decimal(str(amount))))
        total = sum(Decimal(a) * self.rates.rate(date, self.accounts[n].currency, self.base) for n, a in parsed)
        if q(total) != 0:
            raise ValueError("unbalanced by %s" % q(total))
        tx = {"date": date, "memo": memo, "lines": parsed}
        self.transactions.append(tx)
        return tx

    def raw_balance(self, name, as_of=None):
        """Sum of the account's lines up to and including as_of, debits positive, in the account's own currency."""
        total = ZERO
        for tx in self.transactions:
            if as_of is not None and tx["date"] >= as_of:
                continue
            total += sum((a for n, a in tx["lines"] if n == name), ZERO)
        return total

    def balance(self, name, as_of=None):
        """Like raw_balance, but positive on the account's normal side (credits positive for liabilities, equity and income)."""
        return self.raw_balance(name, as_of) * self.accounts[name].sign()
