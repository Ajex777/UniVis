"""Structured YAML configuration for the PIKA raw format."""

from __future__ import annotations

from dataclasses import dataclass, replace
from importlib.resources import files
from pathlib import Path
from typing import Any

import yaml

from univis.formats.pika_raw.options import PikaSyncOptions


@dataclass(frozen=True)
class PikaCameraConfig:
    """One configured PIKA camera stream."""

    key: str
    label: str
    path: str
    suffixes: tuple[str, ...]


@dataclass(frozen=True)
class PikaLayoutConfig:
    """Configured PIKA raw directory layout."""

    episode_pattern: str
    instruction_file: str
    left_camera: PikaCameraConfig
    right_camera: PikaCameraConfig
    left_pose_path: str
    right_pose_path: str
    pose_fields: tuple[str, ...]
    left_gripper_path: str
    right_gripper_path: str


@dataclass(frozen=True)
class PikaRawFormatConfig:
    """Complete PIKA raw format config loaded from YAML."""

    layout: PikaLayoutConfig
    sync: PikaSyncOptions

    @classmethod
    def load(cls, path: Path | str | None = None) -> "PikaRawFormatConfig":
        """Load a config from YAML, using the packaged default when omitted."""

        config_path = Path(path) if path else _default_config_resource()
        payload = _read_yaml(config_path)
        return cls(layout=_layout_from_payload(payload), sync=_sync_from_payload(payload))

    def with_sync_options(self, options: PikaSyncOptions | None) -> "PikaRawFormatConfig":
        """Return the same layout with optional runtime sync overrides."""

        return replace(self, sync=options) if options is not None else self


def _default_config_resource() -> Any:
    """Return the package resource for the default YAML config."""

    return files("univis.formats.pika_raw.config").joinpath("default.yaml")


def _read_yaml(path: Any) -> dict[str, Any]:
    """Read a YAML file and require a mapping at the root."""

    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"PIKA config root must be a mapping: {path}")
    return payload


def _layout_from_payload(payload: dict[str, Any]) -> PikaLayoutConfig:
    """Parse the structured source layout section."""

    source = _mapping(payload, "source")
    cameras = _mapping(source, "cameras")
    pose = _mapping(source, "pose")
    gripper = _mapping(source, "gripper")
    fields = pose.get("fields") or ["x", "y", "z", "roll", "pitch", "yaw"]
    return PikaLayoutConfig(
        episode_pattern=str(source.get("episode_pattern", "episode*")),
        instruction_file=str(source.get("instruction_file", "instructions.json")),
        left_camera=_camera_config(_mapping(cameras, "left_wrist")),
        right_camera=_camera_config(_mapping(cameras, "right_wrist")),
        left_pose_path=str(pose["left_path"]),
        right_pose_path=str(pose["right_path"]),
        pose_fields=tuple(str(item) for item in fields),
        left_gripper_path=str(gripper["left_path"]),
        right_gripper_path=str(gripper["right_path"]),
    )


def _camera_config(payload: dict[str, Any]) -> PikaCameraConfig:
    """Parse one camera subsection."""

    suffixes = tuple(str(item).lower() for item in payload.get("suffixes", []))
    if not suffixes:
        raise ValueError("PIKA camera config requires non-empty suffixes")
    return PikaCameraConfig(
        key=str(payload["key"]),
        label=str(payload.get("label", payload["key"])),
        path=str(payload["path"]),
        suffixes=suffixes,
    )


def _sync_from_payload(payload: dict[str, Any]) -> PikaSyncOptions:
    """Parse sync and processing sections into synchronizer options."""

    sync = _mapping(payload, "sync")
    processing = _mapping(payload, "processing")
    trim = _mapping(processing, "static_trim")
    rebase = _mapping(processing, "pose_rebase")
    gripper = _mapping(processing, "gripper_normalization")
    return PikaSyncOptions(
        camera_tolerance_ms=float(sync.get("camera_tolerance_ms", 30.0)),
        pose_tolerance_ms=float(sync.get("pose_tolerance_ms", 30.0)),
        min_frames=int(sync.get("min_frames", 50)),
        downsample_rate=float(sync.get("downsample_rate", 1.0)),
        gripper_key=str(gripper.get("key", "distance")),
        gripper_min=float(gripper.get("min", 0.0)),
        gripper_max=float(gripper.get("max", 0.095)),
        trim_static_boundaries=bool(trim.get("enabled", True)),
        static_translation_m=float(trim.get("translation_m", 0.02)),
        static_rotation_deg=float(trim.get("rotation_deg", 5.0)),
        rebase_to_first_frame=bool(rebase.get("enabled", True)),
    )


def _mapping(payload: dict[str, Any], key: str) -> dict[str, Any]:
    """Return one required nested mapping from a YAML payload."""

    value = payload.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"PIKA config section `{key}` must be a mapping")
    return value
