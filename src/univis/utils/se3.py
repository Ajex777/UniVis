"""Small SE(3) helpers used by standalone raw-data adapters."""

from __future__ import annotations

import numpy as np


def pose_xyzrpy_to_matrix(pose_xyzrpy: np.ndarray) -> np.ndarray:
    """Convert xyz+rpy rows to 4x4 transform matrices.

    Inputs:
        pose_xyzrpy: Array shaped `(6,)` or `(N, 6)` with radians xyz Euler angles.
    Output:
        Transform matrix shaped `(4, 4)` for one pose or `(N, 4, 4)` for a batch.
    """

    poses, is_single = _batched(pose_xyzrpy, (6,), "pose_xyzrpy")
    mats = np.tile(np.eye(4, dtype=np.float32), (poses.shape[0], 1, 1))
    mats[:, :3, :3] = _rotation_xyz(poses[:, 3:6])
    mats[:, :3, 3] = poses[:, :3]
    return mats[0] if is_single else mats


def matrix_to_pose_xyz6d(mats: np.ndarray) -> np.ndarray:
    """Convert 4x4 transforms to xyz + first two rotation columns.

    Inputs:
        mats: Array shaped `(4, 4)` or `(N, 4, 4)`.
    Output:
        Pose rows shaped `(9,)` or `(N, 9)` matching the dexechain convention.
    """

    batch, is_single = _batched(mats, (4, 4), "mats")
    rot6d = np.concatenate([batch[:, :3, 0], batch[:, :3, 1]], axis=1)
    pose = np.concatenate([batch[:, :3, 3], rot6d], axis=1).astype(np.float32)
    return pose[0] if is_single else pose


def _rotation_xyz(rpy: np.ndarray) -> np.ndarray:
    """Return matrices matching `scipy.Rotation.from_euler("xyz", ...)`."""

    roll, pitch, yaw = rpy[:, 0], rpy[:, 1], rpy[:, 2]
    cr, sr = np.cos(roll), np.sin(roll)
    cp, sp = np.cos(pitch), np.sin(pitch)
    cy, sy = np.cos(yaw), np.sin(yaw)
    mats = np.empty((rpy.shape[0], 3, 3), dtype=np.float32)
    mats[:, 0, 0] = cy * cp
    mats[:, 0, 1] = cy * sp * sr - sy * cr
    mats[:, 0, 2] = cy * sp * cr + sy * sr
    mats[:, 1, 0] = sy * cp
    mats[:, 1, 1] = sy * sp * sr + cy * cr
    mats[:, 1, 2] = sy * sp * cr - cy * sr
    mats[:, 2, 0] = -sp
    mats[:, 2, 1] = cp * sr
    mats[:, 2, 2] = cp * cr
    return mats


def _batched(array: np.ndarray, item_shape: tuple[int, ...], name: str) -> tuple[np.ndarray, bool]:
    arr = np.asarray(array, dtype=np.float32)
    is_single = arr.shape == item_shape
    if is_single:
        arr = arr[None, ...]
    if arr.ndim != len(item_shape) + 1 or arr.shape[1:] != item_shape:
        raise ValueError(f"expected {name} shape {item_shape} or batched, got {arr.shape}")
    return arr, is_single
