import re


def slugify(text):
    """Lowercase, replace each run of non-alphanumerics with a single hyphen, strip hyphens at both ends."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
