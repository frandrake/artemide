"""ULID generation and validation."""
from __future__ import annotations

import ulid

_ULID_ALPHABET = set("0123456789ABCDEFGHJKMNPQRSTVWXYZ")


def new_ulid() -> str:
    return str(ulid.new())


def is_valid_ulid(s: str) -> bool:
    if not isinstance(s, str) or len(s) != 26:
        return False
    return all(c in _ULID_ALPHABET for c in s.upper())
