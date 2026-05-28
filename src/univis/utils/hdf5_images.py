"""Helpers for dexechain-style HDF5 image chunks."""

from __future__ import annotations

from io import BytesIO

import h5py
import numpy as np
from PIL import Image

from univis.domain.policy_episode import CameraStream

try:
    import h5ffmpeg  # noqa: F401
except Exception:
    pass


def hdf5_camera_keys(images_group: h5py.Group) -> list[str]:
    """Return real camera keys from `observations/images`."""

    return [
        key
        for key in images_group.keys()
        if not key.endswith(("_index", "_start"))
    ]


def camera_streams_from_image_group(images_group: h5py.Group) -> list[CameraStream]:
    """Infer camera metadata from the first stored image chunk."""

    streams: list[CameraStream] = []
    for key in hdf5_camera_keys(images_group):
        height, width = _camera_hw(images_group[key])
        streams.append(CameraStream(key=key, label=key, width=width, height=height))
    return streams


def read_hdf5_image_frame(
    images_group: h5py.Group,
    camera_key: str,
    frame_index: int,
) -> np.ndarray:
    """Read one BGR/RGB frame from script-compatible HDF5 image storage."""

    if camera_key not in images_group:
        raise KeyError(f"camera not found: {camera_key}")
    camera_node = images_group[camera_key]
    if isinstance(camera_node, h5py.Dataset):
        frame = camera_node[int(frame_index)]
        return _ensure_bhwc_frame(np.asarray(frame))
    if not isinstance(camera_node, h5py.Group):
        raise TypeError(f"unsupported camera node: {camera_key}")

    chunk_id = _chunk_id_for_frame(images_group, camera_key, frame_index)
    chunk_key = str(chunk_id)
    if chunk_key not in camera_node:
        raise KeyError(f"missing chunk {chunk_key} for camera {camera_key}")
    chunk = _chunk_to_bhwc(np.asarray(camera_node[chunk_key][:]))
    local_index = int(frame_index) - _chunk_start(images_group, camera_key, chunk_id)
    local_index = max(0, min(local_index, chunk.shape[0] - 1))
    return _ensure_bhwc_frame(chunk[local_index])


def encode_frame_png(frame: np.ndarray, *, source_order: str = "bgr") -> bytes:
    """Encode a frame for browser display."""

    arr = _uint8_frame(frame)
    if arr.ndim == 3 and arr.shape[2] == 3 and source_order == "bgr":
        arr = arr[:, :, ::-1]
    image = Image.fromarray(arr)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _camera_hw(node: h5py.Dataset | h5py.Group) -> tuple[int, int]:
    if isinstance(node, h5py.Dataset):
        shape = node.shape
        if len(shape) == 4:
            return int(shape[1]), int(shape[2])
        if len(shape) == 3:
            return int(shape[1]), int(shape[2] // 3)
    if isinstance(node, h5py.Group):
        chunk_keys = sorted(node.keys(), key=lambda value: int(value))
        if chunk_keys:
            shape = node[chunk_keys[0]].shape
            if len(shape) == 4:
                return int(shape[1]), int(shape[2])
            if len(shape) == 3:
                return int(shape[1]), int(shape[2] // 3)
    return 360, 640


def _chunk_to_bhwc(data: np.ndarray, channels: int = 3) -> np.ndarray:
    if data.ndim == 4:
        return data
    if data.ndim == 3:
        frames, height, width = data.shape
        return data.reshape(frames, height, width // channels, channels)
    raise ValueError(f"unsupported image chunk shape: {data.shape}")


def _ensure_bhwc_frame(frame: np.ndarray) -> np.ndarray:
    if frame.ndim == 3:
        return frame
    if frame.ndim == 2 and frame.shape[1] % 3 == 0:
        return frame.reshape(frame.shape[0], frame.shape[1] // 3, 3)
    return frame


def _chunk_id_for_frame(
    images_group: h5py.Group,
    camera_key: str,
    frame_index: int,
) -> int:
    index_key = f"{camera_key}_index"
    if index_key in images_group:
        index = np.asarray(images_group[index_key][:])
        frame_index = max(0, min(int(frame_index), index.shape[0] - 1))
        return int(index[frame_index])
    starts = _chunk_starts(images_group, camera_key)
    return max(0, int(np.searchsorted(starts, int(frame_index), side="right") - 1))


def _chunk_start(images_group: h5py.Group, camera_key: str, chunk_id: int) -> int:
    starts = _chunk_starts(images_group, camera_key)
    if starts.size == 0:
        return 0
    chunk_id = max(0, min(int(chunk_id), starts.shape[0] - 1))
    return int(starts[chunk_id])


def _chunk_starts(images_group: h5py.Group, camera_key: str) -> np.ndarray:
    start_key = f"{camera_key}_start"
    if start_key not in images_group:
        return np.asarray([0], dtype=np.int64)
    return np.asarray(images_group[start_key][:], dtype=np.int64)


def _uint8_frame(frame: np.ndarray) -> np.ndarray:
    arr = np.asarray(frame)
    if arr.dtype == np.uint8:
        return arr
    if np.issubdtype(arr.dtype, np.floating):
        arr = np.clip(arr, 0.0, 1.0) * 255.0
    return np.clip(arr, 0, 255).astype(np.uint8)
