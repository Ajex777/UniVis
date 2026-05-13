"""Color helpers for deterministic fake visual data."""

from __future__ import annotations


PALETTE = [
    "#14785f",
    "#b87300",
    "#1f5f99",
    "#9b4d5f",
    "#476a2c",
    "#6f5a8f",
]


def color_for_key(key: str, offset: int = 0) -> str:
    """Return a stable palette color for a string key.

    Inputs:
        key: Any stable identifier.
        offset: Optional integer offset for related color variants.
    Output:
        Hex color string.
    """

    total = sum(ord(ch) for ch in key) + int(offset)
    return PALETTE[total % len(PALETTE)]
