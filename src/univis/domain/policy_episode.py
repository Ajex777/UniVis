"""Core data models for synchronized PolicyEpisode visualization.

The models in this file intentionally avoid dependencies on robot-specific
packages. They describe the stable API contract shared by raw data adapters,
HDF5 adapters, and future exporters.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class CameraStream(BaseModel):
    """Metadata for one image observation stream.

    Inputs:
        key: Stable camera key used by APIs and UI slots.
        label: Human-readable display name.
        width: Frame width in pixels.
        height: Frame height in pixels.
        kind: Observation type, such as rgb, depth, or fisheye.
    Output:
        Serializable camera metadata for frontend layout selection.
    """

    key: str
    label: str
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    kind: str = "rgb"


class ArmFrame(BaseModel):
    """EEF pose and gripper value for one arm at one synchronized frame.

    Inputs:
        xyz: End-effector position as [x, y, z].
        rot6d: Rotation in 6D representation.
        gripper: Normalized gripper value.
    Output:
        Serializable arm state consumed by the viewer.
    """

    xyz: list[float] = Field(min_length=3, max_length=3)
    rot6d: list[float] = Field(min_length=6, max_length=6)
    gripper: float


class PolicyFrame(BaseModel):
    """Synchronized policy frame containing dual-arm state.

    Inputs:
        index: Local frame index.
        timestamp: Frame timestamp in seconds.
        left: Left arm EEF pose and gripper.
        right: Right arm EEF pose and gripper.
    Output:
        Serializable time-aligned frame data.
    """

    index: int = Field(ge=0)
    timestamp: float = Field(ge=0)
    left: ArmFrame
    right: ArmFrame


class Annotation(BaseModel):
    """Episode-level annotation state.

    Inputs:
        language_prompt: Main language instruction.
        review_status: Whole-episode review status.
        notes: Optional reviewer notes.
        quality_tags: Optional quality tags.
    Output:
        Serializable annotation state used by the UI and API.
    """

    language_prompt: str = ""
    review_status: Literal["pending", "accepted", "rejected"] = "pending"
    notes: str = ""
    quality_tags: list[str] = Field(default_factory=list)


class ReachabilityOverlay(BaseModel):
    """Frame-level reachability hints for visualization.

    Inputs:
        reachable: Per-frame boolean flags.
        reasons: Per-frame reason text, usually empty for reachable frames.
    Output:
        Lightweight overlay consumed by trajectory and timeline views.
    """

    reachable: list[bool]
    reasons: list[str]


class PolicyEpisodeMetadata(BaseModel):
    """Episode metadata without the heavy trajectory payload.

    Inputs:
        episode_id: Stable episode identifier.
        title: Display title.
        num_frames: Number of synchronized frames.
        fps: Preview playback FPS.
        cameras: Variable camera observation list.
        annotation: Episode annotation.
        reachability: Optional frame-level reachability overlay.
    Output:
        Metadata response for episode selection and viewer setup.
    """

    episode_id: str
    title: str
    num_frames: int = Field(gt=0)
    fps: float = Field(gt=0)
    cameras: list[CameraStream]
    annotation: Annotation
    reachability: ReachabilityOverlay | None = None

    @model_validator(mode="after")
    def validate_episode_metadata(self) -> "PolicyEpisodeMetadata":
        """Validate camera keys and reachability shape.

        Inputs:
            Self metadata payload after field parsing.
        Output:
            The same metadata object if camera keys are unique and optional
            reachability arrays match `num_frames`.
        """

        keys = [camera.key for camera in self.cameras]
        if len(keys) != len(set(keys)):
            raise ValueError("camera keys must be unique")
        if self.reachability is not None:
            if len(self.reachability.reachable) != self.num_frames:
                raise ValueError("reachability flags must match num_frames")
            if len(self.reachability.reasons) != self.num_frames:
                raise ValueError("reachability reasons must match num_frames")
        return self


class PolicyEpisode(BaseModel):
    """Complete synchronized episode used by Phase 00 APIs.

    Inputs:
        metadata: Lightweight episode metadata.
        frames: Synchronized dual-arm frames.
    Output:
        Full PolicyEpisode payload for API-backed visualization.
    """

    metadata: PolicyEpisodeMetadata
    frames: list[PolicyFrame]

    @model_validator(mode="after")
    def validate_episode_shape(self) -> "PolicyEpisode":
        """Validate synchronized frame shape.

        Inputs:
            Self episode payload after field parsing.
        Output:
            The same episode when frame count, indices, and timestamps are
            compatible with the metadata contract.
        """

        if len(self.frames) != self.metadata.num_frames:
            raise ValueError("frames length must match metadata.num_frames")
        previous_timestamp = -1.0
        for expected_index, frame in enumerate(self.frames):
            if frame.index != expected_index:
                raise ValueError("frame indices must be contiguous from zero")
            if frame.timestamp < previous_timestamp:
                raise ValueError("frame timestamps must be non-decreasing")
            previous_timestamp = frame.timestamp
        return self
