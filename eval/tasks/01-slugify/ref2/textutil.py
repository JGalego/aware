import re


def slugify(text, max_len=None):
    """Lowercase, replace each run of non-alphanumerics with a single hyphen, strip hyphens at both ends."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    if max_len is None or len(slug) <= max_len:
        return slug
    if slug[max_len] == "-":
        return slug[:max_len].strip("-")
    head = slug[:max_len].rpartition("-")[0]
    return (head or slug[:max_len]).strip("-")
