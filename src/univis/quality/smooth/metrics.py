"""Smoothness metric helpers."""

from __future__ import annotations

import numpy as np


def trajectory_smoothness_acceleration(values: np.ndarray, dt: float) -> tuple[float, float]:
    """Return acceleration cost and max acceleration magnitude."""

    arr = _as_trajectory(values)
    if arr.shape[0] < 3:
        return 0.0, 0.0
    acceleration = np.diff(arr, n=2, axis=0) / float(dt) ** 2
    norm = np.linalg.norm(acceleration, axis=1)
    return float(np.mean(norm**2) * dt), float(np.max(norm))


def trajectory_smoothness_jerk(values: np.ndarray, dt: float) -> tuple[float, float]:
    """Return jerk cost and max jerk magnitude."""

    arr = _as_trajectory(values)
    if arr.shape[0] < 4:
        return 0.0, 0.0
    jerk = np.diff(arr, n=3, axis=0) / float(dt) ** 3
    norm = np.linalg.norm(jerk, axis=1)
    return float(np.mean(norm**2) * dt), float(np.max(norm))


def _as_trajectory(values: np.ndarray) -> np.ndarray:
    """Validate and normalize trajectory arrays."""

    arr = np.asarray(values, dtype=np.float64)
    if arr.ndim == 1:
        arr = arr.reshape(-1, 1)
    if arr.ndim != 2:
        raise ValueError(f"trajectory values must be 2D, got {arr.shape}")
    return arr
