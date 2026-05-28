"""Preprocessor factory — creates the built-in preprocessing components."""

from __future__ import annotations

from univis.preprocessors.action_mask import ActionMaskPreprocessor
from univis.preprocessors.image_mask import ImageMaskPreprocessor


def load_preprocessors() -> list:
    """Return all built-in preprocessor instances."""
    return [
        ActionMaskPreprocessor("left"),
        ActionMaskPreprocessor("right"),
        ImageMaskPreprocessor("left"),
        ImageMaskPreprocessor("right"),
    ]
