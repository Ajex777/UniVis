"""Structured YAML settings for Dexforce W1 teleop raw format."""

from __future__ import annotations

from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class W1CameraConfig:
    """One camera stream declared by the W1 teleop config."""

    key: str
    label: str
    camera_type: str
    place: str
    path: str
    suffixes: tuple[str, ...]


@dataclass(frozen=True)
class W1ArmQposConfig:
    """Qpos names for one W1 arm and gripper."""

    joint_names: tuple[str, ...]
    gripper_name: str


@dataclass(frozen=True)
class W1KinematicsConfig:
    """W1 FK settings distilled from dexechain FK usage."""

    urdf_path: str
    robot_type: str
    arm_kind: str
    left_end_frame: str
    right_end_frame: str
    left_root_without_waist: str
    right_root_without_waist: str
    waist_root: str
    has_waist: bool
    fail_policy: str


@dataclass(frozen=True)
class W1SyncConfig:
    """Synchronization knobs for W1 teleop raw data."""

    reference_camera: str
    camera_tolerance_ms: float
    qpos_tolerance_ms: float
    min_frames: int


@dataclass(frozen=True)
class W1TeleopConfig:
    """Complete W1 teleop format config loaded from YAML."""

    episode_pattern: str
    metadata_file: str
    qpos_pattern: str
    instruction_field: str
    cameras: tuple[W1CameraConfig, ...]
    joint_order: tuple[str, ...]
    waist_joint_names: tuple[str, ...]
    left_arm: W1ArmQposConfig
    right_arm: W1ArmQposConfig
    sync: W1SyncConfig
    kinematics: W1KinematicsConfig
    gripper_ranges: dict[str, tuple[float, float]]

    @classmethod
    def load(cls, path: Path | str | None = None) -> "W1TeleopConfig":
        """Load W1 teleop config from YAML, using packaged defaults."""

        config_path = Path(path) if path else files("univis.formats.dexforce_w1_teleop.config").joinpath("default.yaml")
        payload = _read_yaml(config_path)
        source = _mapping(payload, "source")
        qpos = _mapping(payload, "qpos")
        body = _mapping(qpos, "body")
        arms = _mapping(qpos, "arms")
        processing = _mapping(payload, "processing")
        return cls(
            episode_pattern=str(source.get("episode_pattern", "*")),
            metadata_file=str(source.get("metadata_file", "metadata.jsonl")),
            qpos_pattern=str(source.get("qpos_pattern", "pose_record_*.json")),
            instruction_field=str(source.get("instruction_field", "language_prompt")),
            cameras=tuple(_camera(item) for item in _mapping(payload, "cameras").values()),
            joint_order=tuple(str(item) for item in qpos.get("joint_order", [])),
            waist_joint_names=tuple(str(item) for item in body.get("waist_joint_names", [])),
            left_arm=_arm(_mapping(arms, "left")),
            right_arm=_arm(_mapping(arms, "right")),
            sync=_sync(_mapping(payload, "sync")),
            kinematics=_kinematics(_mapping(payload, "kinematics")),
            gripper_ranges=_grippers(_mapping(processing, "gripper_normalization")),
        )

    def indices_for(self, names: tuple[str, ...]) -> list[int]:
        """Return qpos indices for configured joint names."""

        index = {name: idx for idx, name in enumerate(self.joint_order)}
        return [index[name] for name in names]


def _read_yaml(path: Any) -> dict[str, Any]:
    """Read YAML and require a mapping root."""

    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"W1 config root must be a mapping: {path}")
    return payload


def _mapping(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"W1 config section `{key}` must be a mapping")
    return value


def _camera(payload: dict[str, Any]) -> W1CameraConfig:
    suffixes = tuple(str(item).lower() for item in payload.get("suffixes", []))
    if not suffixes:
        raise ValueError("W1 camera config requires suffixes")
    return W1CameraConfig(
        key=str(payload["key"]),
        label=str(payload.get("label", payload["key"])),
        camera_type=str(payload["camera_type"]),
        place=str(payload["place"]),
        path=str(payload["path"]),
        suffixes=suffixes,
    )


def _arm(payload: dict[str, Any]) -> W1ArmQposConfig:
    return W1ArmQposConfig(
        joint_names=tuple(str(item) for item in payload.get("joint_names", [])),
        gripper_name=str(payload["gripper_name"]),
    )


def _sync(payload: dict[str, Any]) -> W1SyncConfig:
    return W1SyncConfig(
        reference_camera=str(payload.get("reference_camera", "head_left")),
        camera_tolerance_ms=float(payload.get("camera_tolerance_ms", 30.0)),
        qpos_tolerance_ms=float(payload.get("qpos_tolerance_ms", 30.0)),
        min_frames=int(payload.get("min_frames", 45)),
    )


def _kinematics(payload: dict[str, Any]) -> W1KinematicsConfig:
    return W1KinematicsConfig(
        urdf_path=str(payload.get("urdf_path", "")),
        robot_type=str(payload.get("robot_type", "DexforceW1")),
        arm_kind=str(payload.get("arm_kind", "anthropomorphic")),
        left_end_frame=str(payload.get("left_end_frame", "left_ee")),
        right_end_frame=str(payload.get("right_end_frame", "right_ee")),
        left_root_without_waist=str(payload.get("left_root_without_waist", "left_arm_base")),
        right_root_without_waist=str(payload.get("right_root_without_waist", "right_arm_base")),
        waist_root=str(payload.get("waist_root", "waist")),
        has_waist=bool(payload.get("has_waist", True)),
        fail_policy=str(payload.get("fail_policy", "error")),
    )


def _grippers(payload: dict[str, Any]) -> dict[str, tuple[float, float]]:
    return {
        side: (float(values.get("min", 0.0)), float(values.get("max", 1.0)))
        for side, values in payload.items()
        if isinstance(values, dict)
    }
