"""Structured YAML configuration for smoothness quality."""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path
from typing import Any

import yaml

from univis.quality.smooth.models import SmoothnessConfig, SmoothnessScopeConfig


class SmoothnessQualityConfig:
    """Loader for smoothness backend configuration."""

    @classmethod
    def load(cls, path: Path | str | None = None) -> SmoothnessConfig:
        """Load smoothness config from YAML, using packaged defaults when omitted."""

        config_path = Path(path) if path else files("univis.quality.smooth.config").joinpath("default.yaml")
        return _smooth_from_payload(_read_yaml(config_path))


def _read_yaml(path: Any) -> dict[str, Any]:
    """Read a YAML file and require a mapping at the root."""

    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"quality config root must be a mapping: {path}")
    return payload


def _smooth_from_payload(payload: dict[str, Any]) -> SmoothnessConfig:
    """Parse smoothness config sections."""

    time = _mapping(payload, "time")
    scopes_payload = _mapping(payload, "scopes")
    scopes: dict[str, SmoothnessScopeConfig] = {}
    for name, scope in scopes_payload.items():
        if not isinstance(scope, dict):
            raise ValueError(f"smoothness scope `{name}` must be a mapping")
        scopes[str(name)] = SmoothnessScopeConfig(
            enabled=bool(scope.get("enabled", True)),
            source=str(scope["source"]),
            acceleration_cost_threshold=float(scope.get("acceleration_cost_threshold", 10.0)),
            jerk_cost_threshold=float(scope.get("jerk_cost_threshold", 200.0)),
        )
    return SmoothnessConfig(
        use_episode_timestamps=bool(time.get("use_episode_timestamps", True)),
        fps_fallback=float(time.get("fps_fallback", 30.0)),
        scopes=scopes,
    )


def _mapping(payload: dict[str, Any], key: str) -> dict[str, Any]:
    """Return one required nested mapping from a YAML payload."""

    value = payload.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"quality config section `{key}` must be a mapping")
    return value
