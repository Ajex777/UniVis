"""Sorting helpers shared by dataset adapters."""

from __future__ import annotations

import re


def natural_sort_key(value: str) -> list[object]:
    """Return a natural sort key for filenames.

    Inputs:
        value: Filename or display string containing optional numeric parts.
    Output:
        Sort key where digit runs compare as integers.
    """

    return [
        int(part) if part.isdigit() else part.lower()
        for part in re.split(r"(\d+)", value)
    ]
