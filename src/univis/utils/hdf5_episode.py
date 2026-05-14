"""Helpers for UniVis PolicyEpisode HDF5 serialization."""

from __future__ import annotations

import json
from typing import Any

import h5py
import numpy as np

from univis.domain.policy_episode import ArmFrame, PolicyFrame

QPOS_DIM = 20
STRING_DTYPE = h5py.string_dtype(encoding="utf-8")


def decode_scalar(value: Any) -> Any:
    """Decode HDF5 scalar values into plain Python values.

    Inputs:
        value: Raw scalar from h5py dataset or attribute.
    Output:
        Decoded Python value, with bytes converted to UTF-8 strings.
    """

    if isinstance(value, bytes):
        return value.decode("utf-8")
    if hasattr(value, "item"):
        item = value.item()
        return item.decode("utf-8") if isinstance(item, bytes) else item
    return value


def frames_to_qpos(frames: list[PolicyFrame]) -> np.ndarray:
    """Convert synchronized frames to current 20D qpos rows.

    Inputs:
        frames: Policy frames with left/right xyz, rot6d, and gripper.
    Output:
        Float32 array shaped `(num_frames, 20)` using
        `[left_pose9, left_gripper, right_pose9, right_gripper]`.
    """

    rows: list[list[float]] = []
    for frame in frames:
        rows.append(
            frame.left.xyz
            + frame.left.rot6d
            + [frame.left.gripper]
            + frame.right.xyz
            + frame.right.rot6d
            + [frame.right.gripper]
        )
    return np.asarray(rows, dtype=np.float32)


def qpos_to_frames(qpos: np.ndarray, fps: float) -> list[PolicyFrame]:
    """Convert qpos rows into synchronized PolicyFrame objects.

    Inputs:
        qpos: Numeric array with at least 20 columns.
        fps: Playback frame rate used to synthesize timestamps.
    Output:
        Policy frames using the first 20 columns of qpos.
    """

    rows = np.asarray(qpos, dtype=np.float32)
    if rows.ndim == 1:
        rows = rows.reshape(1, -1)
    if rows.ndim != 2 or rows.shape[1] < QPOS_DIM:
        raise ValueError(f"expected qpos shape (N, >=20), got {rows.shape}")
    frames: list[PolicyFrame] = []
    for index, row in enumerate(rows[:, :QPOS_DIM]):
        left = ArmFrame(
            xyz=row[0:3].astype(float).tolist(),
            rot6d=row[3:9].astype(float).tolist(),
            gripper=float(row[9]),
        )
        right = ArmFrame(
            xyz=row[10:13].astype(float).tolist(),
            rot6d=row[13:19].astype(float).tolist(),
            gripper=float(row[19]),
        )
        frames.append(
            PolicyFrame(index=index, timestamp=index / float(fps), left=left, right=right)
        )
    return frames


def read_string_dataset(root: h5py.Group, key: str, default: str = "") -> str:
    """Read an optional string dataset.

    Inputs:
        root: HDF5 group or file.
        key: Dataset key.
        default: Value returned when key is absent.
    Output:
        Decoded string value.
    """

    if key not in root:
        return default
    value = decode_scalar(root[key][()])
    return str(value or "")


def write_string_dataset(root: h5py.Group, key: str, value: str) -> None:
    """Replace a string dataset.

    Inputs:
        root: HDF5 group or file.
        key: Dataset key.
        value: UTF-8 string to store.
    Output:
        Mutates the HDF5 file by replacing the dataset.
    """

    if key in root:
        del root[key]
    root.create_dataset(key, data=str(value), dtype=STRING_DTYPE)


def json_dumps(value: Any) -> str:
    """Serialize metadata as compact UTF-8 JSON text.

    Inputs:
        value: JSON-compatible value.
    Output:
        Compact JSON string.
    """

    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
