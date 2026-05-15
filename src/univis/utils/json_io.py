"""JSON helpers shared by file-backed adapters."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def read_json(path: Path) -> Any:
    """Read UTF-8 JSON from disk.

    Inputs:
        path: JSON file path.
    Output:
        Parsed JSON payload.
    """

    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    """Write UTF-8 JSON to disk.

    Inputs:
        path: Destination path.
        payload: JSON-compatible object.
    Output:
        Mutates the file at `path`.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
