"""Image file helpers for raw dataset preview."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image

_SERVE_AS_IS = {"image/jpeg", "image/png"}


def image_size(path: Path) -> tuple[int, int]:
    """Read image width and height without keeping the file open.

    Inputs:
        path: Image file path.
    Output:
        `(width, height)` in pixels.
    """

    with Image.open(path) as image:
        return int(image.width), int(image.height)


def image_file_to_png(path: Path) -> bytes:
    """Encode an image file as browser-displayable PNG bytes.

    Inputs:
        path: Source image path readable by Pillow.
    Output:
        PNG-encoded RGB bytes.
    """

    with Image.open(path) as image:
        rgb = image.convert("RGB")
        buffer = BytesIO()
        rgb.save(buffer, format="PNG")
        return buffer.getvalue()


def serve_image_file(path: Path) -> tuple[bytes, str]:
    """Serve an on-disk image as efficient browser-displayable bytes.

    JPEG and PNG files are served as-is to avoid re-encoding cost.
    Other formats are converted to PNG.

    Inputs:
        path: Source image path readable by Pillow.
    Output:
        `(data, media_type)` ready for an HTTP response.
    """

    suffix = path.suffix.lower()
    media = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}.get(suffix)
    if media in _SERVE_AS_IS:
        return path.read_bytes(), media
    return image_file_to_png(path), "image/png"
