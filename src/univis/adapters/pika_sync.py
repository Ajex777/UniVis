"""PIKA raw timestamp synchronization matching the legacy converter."""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any

import numpy as np

from univis.adapters.pika_manifest import PikaEpisodeManifest
from univis.utils.json_io import read_json
from univis.utils.se3 import matrix_to_pose_xyz6d, pose_xyzrpy_to_matrix


@dataclass(frozen=True)
class PikaSyncOptions:
    """Synchronization knobs copied from `pika_raw_to_compressed_hdf5.py`."""

    camera_tolerance_ms: float = 30.0
    pose_tolerance_ms: float = 30.0
    min_frames: int = 50
    downsample_rate: float = 1.0
    gripper_key: str = "distance"
    gripper_min: float = 0.0
    gripper_max: float = 0.095


@dataclass(frozen=True)
class PikaSyncResult:
    """Synchronized PIKA episode payload before PolicyEpisode conversion."""

    qpos: np.ndarray
    timestamps: np.ndarray
    image_paths: dict[str, list[Path]]


class PikaEpisodeSynchronizer:
    """Synchronize one PIKA raw episode into qpos rows and image references."""

    def __init__(self, options: PikaSyncOptions | None = None) -> None:
        """Initialize with converter-compatible options."""

        self.options = options or PikaSyncOptions()

    def synchronize(self, manifest: PikaEpisodeManifest) -> PikaSyncResult:
        """Build synchronized qpos rows for one episode."""

        opt = self.options
        left_cam_ts, left_cam_paths = _list_timestamped_files(
            manifest.left_camera_dir, [".jpg", ".jpeg", ".png"]
        )
        right_cam_ts, right_cam_paths = _list_timestamped_files(
            manifest.right_camera_dir, [".jpg", ".jpeg", ".png"]
        )
        left_pose_ts, left_pose = _load_pose_series(manifest.left_pose_dir)
        right_pose_ts, right_pose = _load_pose_series(manifest.right_pose_dir)
        left_grip_ts, left_grip = _load_gripper_series(
            manifest.left_gripper_dir, opt.gripper_key
        )
        right_grip_ts, right_grip = _load_gripper_series(
            manifest.right_gripper_dir, opt.gripper_key
        )
        right_ids, right_dist = _nearest_indices_and_distances(left_cam_ts, right_cam_ts)
        pose_tol = opt.pose_tolerance_ms / 1000.0
        valid = right_dist <= (opt.camera_tolerance_ms / 1000.0)
        valid &= _valid_interpolation_mask(left_cam_ts, left_pose_ts, pose_tol)
        valid &= _valid_interpolation_mask(right_cam_ts[right_ids], right_pose_ts, pose_tol)
        valid &= _valid_interpolation_mask(left_cam_ts, left_grip_ts, pose_tol)
        valid &= _valid_interpolation_mask(right_cam_ts[right_ids], right_grip_ts, pose_tol)
        if int(valid.sum()) < opt.min_frames:
            raise ValueError(f"valid frames {int(valid.sum())} < min_frames {opt.min_frames}")

        left_paths = [path for path, keep in zip(left_cam_paths, valid) if keep]
        right_paths = [right_cam_paths[idx] for idx, keep in zip(right_ids, valid) if keep]
        ref_ts = left_cam_ts[valid]
        right_ref_ts = right_cam_ts[right_ids[valid]]
        left_pose_interp = _interpolate_series(left_pose_ts, left_pose, ref_ts)
        right_pose_interp = _interpolate_series(right_pose_ts, right_pose, right_ref_ts)
        start, end = _trim_static_boundary_frames(left_pose_interp, right_pose_interp)
        left_paths, right_paths = left_paths[start:end], right_paths[start:end]
        ref_ts, right_ref_ts = ref_ts[start:end], right_ref_ts[start:end]
        left_pose_interp = left_pose_interp[start:end]
        right_pose_interp = right_pose_interp[start:end]
        if ref_ts.shape[0] < opt.min_frames:
            raise ValueError(f"frames after trimming {ref_ts.shape[0]} < min_frames {opt.min_frames}")

        keep = _select_downsample_indices(ref_ts.shape[0], opt.downsample_rate)
        left_paths = [left_paths[idx] for idx in keep]
        right_paths = [right_paths[idx] for idx in keep]
        ref_ts, right_ref_ts = ref_ts[keep], right_ref_ts[keep]
        left_pose_interp, right_pose_interp = left_pose_interp[keep], right_pose_interp[keep]
        left_grip = _interpolate_series(left_grip_ts, left_grip, ref_ts)
        right_grip = _interpolate_series(right_grip_ts, right_grip, right_ref_ts)
        qpos = _build_policy_vector(
            _rebase_pose_series_to_first_frame(left_pose_interp),
            _normalize_gripper(left_grip, opt.gripper_min, opt.gripper_max),
            _rebase_pose_series_to_first_frame(right_pose_interp),
            _normalize_gripper(right_grip, opt.gripper_min, opt.gripper_max),
        )
        return PikaSyncResult(
            qpos=qpos,
            timestamps=ref_ts - float(ref_ts[0]),
            image_paths={"cam_left_wrist": left_paths, "cam_right_wrist": right_paths},
        )


def _list_timestamped_files(dir_path: Path, suffixes: list[str]) -> tuple[np.ndarray, list[Path]]:
    items: list[tuple[float, Path]] = []
    suffix_set = {suffix.lower() for suffix in suffixes}
    for path in dir_path.iterdir():
        if path.is_file() and path.suffix.lower() in suffix_set:
            try:
                items.append((float(path.stem), path))
            except ValueError:
                continue
    if not items:
        raise FileNotFoundError(f"no timestamped files found in {dir_path}")
    items.sort(key=lambda item: item[0])
    return np.asarray([item[0] for item in items], dtype=np.float64), [item[1] for item in items]


def _load_pose_series(dir_path: Path) -> tuple[np.ndarray, np.ndarray]:
    ts, paths = _list_timestamped_files(dir_path, [".json"])
    rows = []
    for path in paths:
        payload = _unwrap_payload(read_json(path))
        rows.append([float(payload[key]) for key in ("x", "y", "z", "roll", "pitch", "yaw")])
    return ts, np.asarray(rows, dtype=np.float32)


def _load_gripper_series(dir_path: Path, key: str) -> tuple[np.ndarray, np.ndarray]:
    ts, paths = _list_timestamped_files(dir_path, [".json"])
    values = []
    for path in paths:
        payload = _unwrap_payload(read_json(path))
        if key not in payload:
            raise KeyError(f"missing gripper key {key} in {path}")
        values.append([float(payload[key])])
    return ts, np.asarray(values, dtype=np.float32)


def _unwrap_payload(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
        return payload["data"]
    if isinstance(payload, dict):
        return payload
    raise ValueError(f"unsupported JSON payload: {type(payload)}")


def _nearest_indices_and_distances(query: np.ndarray, source: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    insert_ids = np.searchsorted(source, query, side="left")
    right_ids = np.clip(insert_ids, 0, source.shape[0] - 1)
    left_ids = np.clip(insert_ids - 1, 0, source.shape[0] - 1)
    left_dist = np.abs(query - source[left_ids])
    right_dist = np.abs(query - source[right_ids])
    use_left = left_dist <= right_dist
    return np.where(use_left, left_ids, right_ids), np.where(use_left, left_dist, right_dist)


def _valid_interpolation_mask(target: np.ndarray, source: np.ndarray, tolerance: float) -> np.ndarray:
    inside = (target >= source[0]) & (target <= source[-1])
    _, nearest = _nearest_indices_and_distances(target, source)
    return inside & (nearest <= tolerance)


def _interpolate_series(source_ts: np.ndarray, values: np.ndarray, target_ts: np.ndarray) -> np.ndarray:
    data = values[:, None] if values.ndim == 1 else values
    out = np.zeros((target_ts.shape[0], data.shape[1]), dtype=np.float32)
    for dim in range(data.shape[1]):
        out[:, dim] = np.interp(target_ts, source_ts, data[:, dim]).astype(np.float32)
    return out


def _rebase_pose_series_to_first_frame(pose_xyzrpy: np.ndarray) -> np.ndarray:
    mats = pose_xyzrpy_to_matrix(pose_xyzrpy)
    first_inv = np.linalg.inv(mats[0]).astype(np.float32)
    return matrix_to_pose_xyz6d(np.matmul(first_inv[None, :, :], mats).astype(np.float32))


def _trim_static_boundary_frames(left: np.ndarray, right: np.ndarray) -> tuple[int, int]:
    trans, rot = 0.02, math.radians(5.0)
    start_static = _static_mask(left, left[0], trans, rot) & _static_mask(right, right[0], trans, rot)
    start = next((max(0, idx - 1) for idx, still in enumerate(start_static) if not still), left.shape[0] - 1)
    end_static = _static_mask(left, left[-1], trans, rot) & _static_mask(right, right[-1], trans, rot)
    end = next((min(left.shape[0], idx + 2) for idx in range(left.shape[0] - 1, -1, -1) if not end_static[idx]), 1)
    if start >= end:
        keep = min(start, left.shape[0] - 1)
        return keep, keep + 1
    return start, end


def _static_mask(poses: np.ndarray, reference: np.ndarray, trans_limit: float, rot_limit: float) -> np.ndarray:
    mats = pose_xyzrpy_to_matrix(poses)
    rel = np.matmul(np.linalg.inv(pose_xyzrpy_to_matrix(reference)[None, :, :]), mats)
    trans = np.linalg.norm(rel[:, :3, 3], axis=1)
    cos_theta = np.clip((np.trace(rel[:, :3, :3], axis1=1, axis2=2) - 1.0) * 0.5, -1.0, 1.0)
    return (trans <= trans_limit) & (np.arccos(cos_theta) <= rot_limit)


def _select_downsample_indices(num_frames: int, rate: float) -> np.ndarray:
    if not (0.0 < rate <= 1.0):
        raise ValueError(f"downsample_rate must be in (0, 1], got {rate}")
    if rate >= 1.0:
        return np.arange(num_frames, dtype=np.int64)
    return np.unique(np.round(np.linspace(0, num_frames - 1, math.ceil(num_frames * rate))).astype(np.int64))


def _normalize_gripper(values: np.ndarray, min_value: float, max_value: float) -> np.ndarray:
    if max_value <= min_value:
        raise ValueError("invalid gripper normalization range")
    return np.clip((values - min_value) / (max_value - min_value), 0.0, 1.0).astype(np.float32)


def _build_policy_vector(left_pose9: np.ndarray, left_grip: np.ndarray, right_pose9: np.ndarray, right_grip: np.ndarray) -> np.ndarray:
    return np.concatenate([left_pose9, left_grip, right_pose9, right_grip], axis=1).astype(np.float32)
