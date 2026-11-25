ASSET, LIABILITY, EQUITY, INCOME, EXPENSE = "asset", "liability", "equity", "income", "expense"
KINDS = (ASSET, LIABILITY, EQUITY, INCOME, EXPENSE)


class Account:
    def __init__(self, name, kind, currency):
        if kind not in KINDS:
            raise ValueError("unknown account kind " + kind)
        self.name = name
        self.kind = kind
        self.currency = currency

    def sign(self):
        """+1 for accounts whose normal balance is a debit (assets, expenses), -1 for the others."""
        return 1 if self.kind in (ASSET, EXPENSE) else -1
