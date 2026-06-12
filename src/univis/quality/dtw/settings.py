"""Structured YAML configuration for DTW quality."""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path
from typing import Any

import yaml

from univis.quality.dtw.models import PoseDTWConfig


class DTWQualityConfig:
    """Loader for DTW backend configuration."""

    @classmethod
    def load(cls, path: Path | str | None = None) -> PoseDTWConfig:
        """Load DTW config from YAML, using packaged defaults when omitted."""

        config_path = Path(path) if path else files("univis.quality.dtw.config").joinpath("default.yaml")
        return _dtw_from_payload(_read_yaml(config_path))


def _read_yaml(path: Any) -> dict[str, Any]:
    """Read a YAML file and require a mapping at the root."""

    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"quality config root must be a mapping: {path}")
    return payload


def _dtw_from_payload(payload: dict[str, Any]) -> PoseDTWConfig:
    """Parse the structured DTW config sections."""

    pose = _mapping(payload, "pose_distance")
    position = _mapping(pose, "position")
    rotation = _mapping(pose, "rotation")
    alignment = _mapping(payload, "alignment")
    window = _mapping(alignment, "window")
    visualization = _mapping(payload, "visualization")
    links = _mapping(visualization, "alignment_links")
    statistics = _mapping(payload, "statistics")
    return PoseDTWConfig(
        pos_scale=float(position.get("scale_m", 0.01)),
        rot_scale_deg=float(rotation.get("scale_deg", 5.0)),
        window_ratio=float(window.get("ratio", 0.2)) if bool(window.get("enabled", True)) else None,
        max_visual_links=int(links.get("max_count", 120)),
        percentile=float(statistics.get("percentile", 95.0)),
    )


def _mapping(payload: dict[str, Any], key: str) -> dict[str, Any]:
    """Return one required nested mapping from a YAML payload."""

    value = payload.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"quality config section `{key}` must be a mapping")
    return value
