"""Hash ID generation utilities for Zeeker."""

import hashlib


def get_hash_id(elements: list[str]) -> str:
    """Generate a deterministic hash ID from multiple fields.

    Args:
        elements: List of strings to hash together

    Returns:
        MD5 hash of the joined elements

    Example:
        >>> get_hash_id(["user123", "post456"])
        'a1b2c3d4e5f6...'
    """
    return hashlib.md5("\x00".join(str(e) for e in elements).encode()).hexdigest()
