"""Small geometry helpers for fake dual-arm trajectories."""

from __future__ import annotations

import math


def lerp(a: float, b: float, t: float) -> float:
    """Linearly interpolate between two floats.

    Inputs:
        a: Start value.
        b: End value.
        t: Interpolation factor in [0, 1].
    Output:
        Interpolated float.
    """

    return float(a + (b - a) * t)


def wave(value: float, phase: float = 0.0) -> float:
    """Compute a smooth sinusoidal value.

    Inputs:
        value: Normalized progress or time value.
        phase: Additional phase in radians.
    Output:
        Sine wave value.
    """

    return float(math.sin(value * math.tau + phase))
