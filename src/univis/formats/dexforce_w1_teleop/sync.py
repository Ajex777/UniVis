"""Timestamp synchronization for Dexforce W1 teleop raw episodes."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json

import numpy as np

from univis.formats.dexforce_w1_teleop.manifest import W1EpisodeManifest
from univis.formats.dexforce_w1_teleop.settings import W1CameraConfig, W1TeleopConfig
from univis.utils.json_io import read_json


@dataclass(frozen=True)
class W1SyncResult:
    """Synchronized W1 teleop payload before PolicyEpisode conversion."""

    qpos: np.ndarray
    timestamps: np.ndarray
    image_paths: dict[str, list[Path]]


class W1EpisodeSynchronizer:
    """Align W1 qpos and camera frames using the configured reference camera."""

    def __init__(self, config: W1TeleopConfig) -> None:
        """Store config used for timestamp matching and interpolation."""

        self.config = config

    def synchronize(self, manifest: W1EpisodeManifest) -> W1SyncResult:
        """Return full qpos rows interpolated to reference-camera timestamps."""

        camera_series = _load_camera_series(manifest)
        ref_camera = _camera_by_key_or_name(self.config, self.config.sync.reference_camera)
        ref_ts, ref_paths = camera_series[ref_camera.key]
        qpos_ts, qpos = _load_qpos(manifest.qpos_path, self.config.joint_order)
        valid = _valid_interpolation_mask(ref_ts, qpos_ts, self.config.sync.qpos_tolerance_ms / 1000.0)
        image_paths = {ref_camera.key: [path for path, keep in zip(ref_paths, valid) if keep]}
        ref_ts = ref_ts[valid]
        if ref_ts.shape[0] < self.config.sync.min_frames:
            raise ValueError(f"valid W1 frames {ref_ts.shape[0]} < min_frames {self.config.sync.min_frames}")
        qpos_interp = _interpolate_series(qpos_ts, qpos, ref_ts)
        for camera in self.config.cameras:
            if camera.key == ref_camera.key:
                continue
            ts, paths = camera_series.get(camera.key, (np.asarray([], dtype=np.float64), []))
            image_paths[camera.key] = _match_camera_paths(ref_ts, ts, paths, self.config.sync.camera_tolerance_ms / 1000.0)
        return W1SyncResult(qpos=qpos_interp, timestamps=ref_ts - float(ref_ts[0]), image_paths=image_paths)


def _load_camera_series(manifest: W1EpisodeManifest) -> dict[str, tuple[np.ndarray, list[Path]]]:
    """Load timestamped camera paths from metadata.jsonl."""

    entries = _read_jsonl(manifest.metadata_path)
    result: dict[str, tuple[np.ndarray, list[Path]]] = {}
    for camera in manifest.cameras:
        items: list[tuple[float, Path]] = []
        for entry in entries:
            if not _matches_camera(entry, camera):
                continue
            timestamp = float(entry["timestamp"])
            path = _resolve_image_path(manifest.episode_dir, camera, str(entry.get("image_path", "")))
            if path.exists():
                items.append((timestamp, path))
        if items:
            items.sort(key=lambda item: item[0])
            result[camera.key] = (
                np.asarray([item[0] for item in items], dtype=np.float64),
                [item[1] for item in items],
            )
    if not result:
        raise FileNotFoundError(f"no W1 camera frames found in metadata: {manifest.metadata_path}")
    return result


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read JSONL metadata rows."""

    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _matches_camera(entry: dict[str, Any], camera: W1CameraConfig) -> bool:
    """Match camera metadata using substring-compatible type/place fields."""

    camera_type = str(entry.get("camera_type", "")).lower()
    return camera.camera_type.lower() in camera_type and camera.place.lower() in camera_type


def _resolve_image_path(root: Path, camera: W1CameraConfig, raw_path: str) -> Path:
    """Resolve image path from metadata with config-path fallback."""

    candidate = root / raw_path
    if candidate.exists():
        return candidate
    return root / camera.path / Path(raw_path).name


def _load_qpos(path: Path, joint_order: tuple[str, ...]) -> tuple[np.ndarray, np.ndarray]:
    """Load sorted qpos timestamps and full rows from pose_record JSON."""

    payload = read_json(path)
    frames = sorted(payload.get("frames", []), key=lambda item: float(item["timestamp"]))
    if not frames:
        raise ValueError(f"W1 qpos file has no frames: {path}")
    ts = np.asarray([float(frame["timestamp"]) for frame in frames], dtype=np.float64)
    rows = [
        [float(frame.get("data", {}).get(joint, 0.0)) for joint in joint_order]
        for frame in frames
    ]
    return ts, np.asarray(rows, dtype=np.float32)


def _valid_interpolation_mask(target: np.ndarray, source: np.ndarray, tolerance: float) -> np.ndarray:
    """Return target timestamps close enough to qpos samples for interpolation."""

    inside = (target >= source[0]) & (target <= source[-1])
    _, nearest = _nearest_indices_and_distances(target, source)
    return inside & (nearest <= tolerance)


def _nearest_indices_and_distances(query: np.ndarray, source: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    insert_ids = np.searchsorted(source, query, side="left")
    right_ids = np.clip(insert_ids, 0, source.shape[0] - 1)
    left_ids = np.clip(insert_ids - 1, 0, source.shape[0] - 1)
    left_dist = np.abs(query - source[left_ids])
    right_dist = np.abs(query - source[right_ids])
    use_left = left_dist <= right_dist
    return np.where(use_left, left_ids, right_ids), np.where(use_left, left_dist, right_dist)


def _interpolate_series(source_ts: np.ndarray, values: np.ndarray, target_ts: np.ndarray) -> np.ndarray:
    data = values[:, None] if values.ndim == 1 else values
    out = np.zeros((target_ts.shape[0], data.shape[1]), dtype=np.float32)
    for dim in range(data.shape[1]):
        out[:, dim] = np.interp(target_ts, source_ts, data[:, dim]).astype(np.float32)
    return out


def _match_camera_paths(ref_ts: np.ndarray, ts: np.ndarray, paths: list[Path], tolerance: float) -> list[Path]:
    """Match non-reference camera frames to reference timestamps."""

    if ts.size == 0 or not paths:
        return []
    indices, dist = _nearest_indices_and_distances(ref_ts, ts)
    return [paths[int(idx)] for idx, delta in zip(indices, dist) if delta <= tolerance]


def _camera_by_key_or_name(config: W1TeleopConfig, token: str) -> W1CameraConfig:
    for camera in config.cameras:
        if token in {camera.key, camera.label} or token.replace("_", "").lower() in camera.key.replace("_", "").lower():
            return camera
    raise KeyError(f"unknown W1 reference camera: {token}")
