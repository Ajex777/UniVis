"""Serializable smoothness quality models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SmoothnessScopeConfig(BaseModel):
    """Configuration for one smoothness trajectory scope."""

    enabled: bool = True
    source: str
    acceleration_cost_threshold: float = Field(default=10.0, gt=0)
    jerk_cost_threshold: float = Field(default=200.0, gt=0)


class SmoothnessConfig(BaseModel):
    """Configuration for single-episode trajectory smoothness checks."""

    use_episode_timestamps: bool = True
    fps_fallback: float = Field(default=30.0, gt=0)
    scopes: dict[str, SmoothnessScopeConfig]


class ArmSmoothnessSummary(BaseModel):
    """Smoothness metrics for one configured trajectory scope."""

    source: str
    acceleration_cost: float
    jerk_cost: float
    max_acceleration: float
    max_jerk: float
    num_frames: int
    dt: float
    passed: bool
    warnings: list[str] = Field(default_factory=list)


class EpisodeSmoothnessReport(BaseModel):
    """Single-episode smoothness report."""

    episode_id: str
    num_frames: int
    passed: bool
    scopes: dict[str, ArmSmoothnessSummary]
