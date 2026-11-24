"""Tiny text helpers (synthetic fixture repository)."""


def slugify(text: str) -> str:
    return text.lower().replace(" ", "-")


def truncate(text: str, limit: int) -> str:
    """Return text cut to `limit` characters INCLUDING a trailing ellipsis when truncated."""
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


def word_count(text: str) -> int:
    return len(text.split(" "))
