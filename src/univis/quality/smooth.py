"""Single-episode trajectory smoothness backend."""

from __future__ import annotations

import numpy as np

from univis.core.components import ComponentInfo
from univis.domain.policy_episode import PolicyEpisode, PolicyFrame
from univis.quality.base import TrajectoryQualityBackend
from univis.quality.models import (
    ArmSmoothnessSummary,
    EpisodeDTWComparison,
    EpisodeSmoothnessReport,
    SelectedEpisodeDTWStats,
    SmoothnessConfig,
    SmoothnessScopeConfig,
)
from univis.quality.settings import QualityConfig


class SmoothnessTrajectoryQualityBackend(TrajectoryQualityBackend):
    """Assess whether one PolicyEpisode has smooth EEF trajectories."""

    def __init__(self, config: SmoothnessConfig | None = None) -> None:
        self.config = config or QualityConfig.load().smoothness

    @classmethod
    def info(cls) -> ComponentInfo:
        return ComponentInfo(
            name="SmoothnessTrajectoryQualityBackend",
            label="Smooth Trajectory",
            aliases=["Smooth"],
            description="Check single-episode EEF acceleration and jerk smoothness.",
        )

    def assess(self, episode: PolicyEpisode) -> EpisodeSmoothnessReport:
        """Compute smoothness metrics for every enabled configured scope."""

        dt = _episode_dt(episode, self.config)
        scopes: dict[str, ArmSmoothnessSummary] = {}
        for name, scope in self.config.scopes.items():
            if not scope.enabled:
                continue
            values = _extract_scope(episode.frames, scope.source)
            scopes[name] = _summarize_scope(values, dt, scope)
        return EpisodeSmoothnessReport(
            episode_id=episode.metadata.episode_id,
            num_frames=episode.metadata.num_frames,
            passed=all(summary.passed for summary in scopes.values()),
            scopes=scopes,
        )

    def compare(
        self,
        current: PolicyEpisode,
        reference: PolicyEpisode,
    ) -> EpisodeDTWComparison:
        """Smoothness is reference-free; use `assess` instead."""

        raise NotImplementedError("smoothness quality does not compare against a reference")

    def selected_stats(
        self,
        episodes: list[PolicyEpisode],
        reference: PolicyEpisode,
    ) -> SelectedEpisodeDTWStats:
        """Smoothness is reference-free; use `assess` episode-by-episode."""

        raise NotImplementedError("smoothness quality does not aggregate DTW stats")


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


def _summarize_scope(
    values: np.ndarray,
    dt: float,
    scope: SmoothnessScopeConfig,
) -> ArmSmoothnessSummary:
    acceleration_cost, max_acceleration = trajectory_smoothness_acceleration(values, dt)
    jerk_cost, max_jerk = trajectory_smoothness_jerk(values, dt)
    warnings: list[str] = []
    if acceleration_cost > scope.acceleration_cost_threshold:
        warnings.append(
            "acceleration_cost "
            f"{acceleration_cost:.4f} > {scope.acceleration_cost_threshold:.4f}"
        )
    if jerk_cost > scope.jerk_cost_threshold:
        warnings.append(f"jerk_cost {jerk_cost:.4f} > {scope.jerk_cost_threshold:.4f}")
    return ArmSmoothnessSummary(
        source=scope.source,
        acceleration_cost=acceleration_cost,
        jerk_cost=jerk_cost,
        max_acceleration=max_acceleration,
        max_jerk=max_jerk,
        num_frames=int(values.shape[0]),
        dt=float(dt),
        passed=not warnings,
        warnings=warnings,
    )


def _episode_dt(episode: PolicyEpisode, config: SmoothnessConfig) -> float:
    """Estimate the scalar step time used by finite differences."""

    if config.use_episode_timestamps and len(episode.frames) >= 2:
        timestamps = np.asarray([frame.timestamp for frame in episode.frames], dtype=np.float64)
        diffs = np.diff(timestamps)
        positive = diffs[diffs > 1e-9]
        if positive.size:
            return float(np.median(positive))
    fps = episode.metadata.fps if episode.metadata.fps > 0 else config.fps_fallback
    return float(1.0 / fps)


def _extract_scope(frames: list[PolicyFrame], source: str) -> np.ndarray:
    """Extract a configured frame source into a `(T, D)` array."""

    side, _, field = source.partition(".")
    if side not in {"left", "right"} or field not in {"xyz", "rot6d"}:
        raise ValueError(f"unsupported smoothness source: {source}")
    rows = []
    for frame in frames:
        arm = frame.left if side == "left" else frame.right
        rows.append(getattr(arm, field))
    return np.asarray(rows, dtype=np.float64)


def _as_trajectory(values: np.ndarray) -> np.ndarray:
    """Validate and normalize trajectory arrays."""

    arr = np.asarray(values, dtype=np.float64)
    if arr.ndim == 1:
        arr = arr.reshape(-1, 1)
    if arr.ndim != 2:
        raise ValueError(f"trajectory values must be 2D, got {arr.shape}")
    return arr
