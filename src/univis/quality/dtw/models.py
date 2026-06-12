"""Serializable DTW quality models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PoseDTWConfig(BaseModel):
    """Configuration for relative pose DTW comparison."""

    pos_scale: float = Field(default=0.01, gt=0)
    rot_scale_deg: float = Field(default=5.0, gt=0)
    window_ratio: float | None = Field(default=0.2, ge=0)
    max_visual_links: int = Field(default=120, ge=1)
    percentile: float = Field(default=95.0, gt=0, lt=100)


class ArmDTWSummary(BaseModel):
    """Summary metrics for one arm DTW alignment."""

    dtw_cost: float
    dtw_cost_normalized: float
    mean_position_error: float
    p95_position_error: float
    max_position_error: float
    final_position_error: float
    mean_rotation_error_deg: float
    p95_rotation_error_deg: float
    max_rotation_error_deg: float
    final_rotation_error_deg: float
    warp_distortion: float
    path_length: int
    length_current: int
    length_reference: int
    length_ratio: float


class ArmDTWAlignment(BaseModel):
    """Alignment payload for one arm."""

    summary: ArmDTWSummary
    warping_path: list[tuple[int, int]]
    visual_links: list[tuple[int, int]]


class EpisodeDTWComparison(BaseModel):
    """Current episode vs reference episode DTW result."""

    current_episode_id: str
    reference_episode_id: str
    left: ArmDTWAlignment
    right: ArmDTWAlignment


class EpisodeDTWScore(BaseModel):
    """Compact per-episode score used by selected episode stats."""

    episode_id: str
    left_dtw_cost_normalized: float
    right_dtw_cost_normalized: float
    left_p95_position_error: float
    right_p95_position_error: float


class SelectedEpisodeDTWStats(BaseModel):
    """Aggregated DTW metrics for selected episodes against one reference."""

    reference_episode_id: str
    selected_episode_ids: list[str]
    left_summary: dict[str, float]
    right_summary: dict[str, float]
    abnormal_episodes: list[EpisodeDTWScore]
