"""PIKA raw synchronization option models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PikaSyncOptions:
    """Synchronization and processing knobs for PIKA raw episodes."""

    camera_tolerance_ms: float = 30.0
    pose_tolerance_ms: float = 30.0
    min_frames: int = 50
    downsample_rate: float = 1.0
    gripper_key: str = "distance"
    gripper_min: float = 0.0
    gripper_max: float = 0.095
    trim_static_boundaries: bool = True
    static_translation_m: float = 0.02
    static_rotation_deg: float = 5.0
    rebase_to_first_frame: bool = True
