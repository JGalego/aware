class Response:
    def __init__(self, status=200, body="", headers=None):
        self.status = status
        self.body = body
        self.headers = dict(headers or {})

    def __repr__(self):
        return "Response(%r, %r, %r)" % (self.status, self.body, self.headers)


class HTTPError(Exception):
    """Raised by a handler to answer with a specific status."""

    def __init__(self, status, message=""):
        super().__init__(message)
        self.status = status
        self.message = message
