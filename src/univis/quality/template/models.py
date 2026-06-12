"""Template models for a UniVis quality feature."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TemplateQualityConfig(BaseModel):
    """Configuration for the template quality backend.

    Inputs:
        min_frames: Single-episode report passes only when the episode has at
            least this many frames.
        max_frame_delta: Pairwise report passes only when current/reference
            frame-count difference is at most this value.
    Output:
        Validated config object consumed by `TemplateQualityBackend`.
    """

    min_frames: int = Field(default=2, ge=1)
    max_frame_delta: int = Field(default=10, ge=0)


class TemplateCompareReport(BaseModel):
    """Pairwise quality report for current/reference comparison."""

    current_episode_id: str
    reference_episode_id: str
    score: float
    passed: bool


class TemplateBatchReport(BaseModel):
    """Batch quality report for selected episodes against one reference."""

    reference_episode_id: str
    selected_episode_ids: list[str]
    mean_score: float | None


class TemplateSingleEpisodeReport(BaseModel):
    """Single-episode quality report without a reference."""

    episode_id: str
    num_frames: int
    passed: bool
