"""Math helpers for relative pose DTW."""

from __future__ import annotations

import math

import numpy as np


def rot6d_to_matrix(rot6d: np.ndarray) -> np.ndarray:
    """Convert 6D rotation representation to rotation matrices."""

    values = np.asarray(rot6d, dtype=np.float64)
    a1 = values[..., 0:3]
    a2 = values[..., 3:6]
    b1 = _safe_normalize(a1)
    projection = np.sum(b1 * a2, axis=-1, keepdims=True) * b1
    b2 = _safe_normalize(a2 - projection)
    b3 = np.cross(b1, b2)
    return np.stack([b1, b2, b3], axis=-1)


def rotation_distance_rad(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Compute geodesic angular distance between rotation matrices."""

    delta = np.swapaxes(a, -1, -2) @ b
    trace = np.trace(delta, axis1=-2, axis2=-1)
    cos_theta = np.clip((trace - 1.0) / 2.0, -1.0, 1.0)
    return np.arccos(cos_theta)


def compute_dtw(cost_matrix: np.ndarray, window: int | None = None) -> tuple[float, list[tuple[int, int]]]:
    """Compute DTW total cost and best path from a pairwise cost matrix."""

    costs = np.asarray(cost_matrix, dtype=np.float64)
    m, n = costs.shape
    if m == 0 or n == 0:
        raise ValueError("DTW trajectories must be non-empty")
    if window is None:
        window = max(m, n)
    window = max(int(window), abs(m - n))
    cumulative = np.full((m + 1, n + 1), np.inf, dtype=np.float64)
    cumulative[0, 0] = 0.0
    for i in range(1, m + 1):
        j_start = max(1, i - window)
        j_end = min(n + 1, i + window + 1)
        for j in range(j_start, j_end):
            cumulative[i, j] = costs[i - 1, j - 1] + min(
                cumulative[i - 1, j],
                cumulative[i, j - 1],
                cumulative[i - 1, j - 1],
            )
    return float(cumulative[m, n]), _backtrack(cumulative)


def warp_distortion(path: list[tuple[int, int]], len_current: int, len_reference: int) -> float:
    """Return mean deviation from diagonal alignment in normalized time."""

    if len_current <= 1 or len_reference <= 1 or not path:
        return 0.0
    return float(np.mean([
        abs((i / (len_current - 1)) - (j / (len_reference - 1)))
        for i, j in path
    ]))


def decimate_path(path: list[tuple[int, int]], max_links: int) -> list[tuple[int, int]]:
    """Return at most `max_links` evenly sampled DTW path pairs."""

    if len(path) <= max_links:
        return path
    indices = np.linspace(0, len(path) - 1, max_links)
    return [path[int(round(index))] for index in indices]


def percentile(values: list[float], q: float) -> float:
    """Return a percentile as a plain float."""

    return float(np.percentile(np.asarray(values, dtype=np.float64), q))


def degrees(values: list[float]) -> list[float]:
    """Convert radians to degrees for metric reporting."""

    return [math.degrees(value) for value in values]


def _safe_normalize(values: np.ndarray) -> np.ndarray:
    """Normalize vectors with fallback for near-zero inputs."""

    norms = np.linalg.norm(values, axis=-1, keepdims=True)
    fallback = np.zeros_like(values)
    fallback[..., 0] = 1.0
    return np.where(norms > 1e-12, values / np.maximum(norms, 1e-12), fallback)


def _backtrack(cumulative: np.ndarray) -> list[tuple[int, int]]:
    """Backtrack a DTW path from a cumulative cost matrix."""

    i, j = cumulative.shape[0] - 1, cumulative.shape[1] - 1
    path: list[tuple[int, int]] = []
    while i > 0 and j > 0:
        path.append((i - 1, j - 1))
        candidates = (
            (cumulative[i - 1, j - 1], i - 1, j - 1),
            (cumulative[i - 1, j], i - 1, j),
            (cumulative[i, j - 1], i, j - 1),
        )
        _, i, j = min(candidates, key=lambda item: item[0])
    while i > 0:
        path.append((i - 1, 0))
        i -= 1
    while j > 0:
        path.append((0, j - 1))
        j -= 1
    path.reverse()
    return path
