"""HTTP error helpers that preserve traceback details for browser debugging."""

from __future__ import annotations

import traceback

from fastapi import HTTPException


def bad_request(exc: Exception) -> HTTPException:
    """Build a 400 response with a short message and full traceback.

    Inputs:
        exc: Original exception from API/service/adapter code.
    Output:
        HTTPException whose detail contains `message` for UI display and
        `traceback` for browser DevTools Network/console inspection.
    """

    return HTTPException(status_code=400, detail=error_detail(exc))


def error_detail(exc: Exception) -> dict[str, str]:
    """Return JSON-serializable exception details."""

    return {
        "message": str(exc),
        "traceback": "".join(
            traceback.format_exception(type(exc), exc, exc.__traceback__)
        ),
    }
