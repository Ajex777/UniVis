"""Dexechain compressed HDF5 schema helpers."""

from __future__ import annotations

from io import BytesIO

import h5py
import numpy as np
from PIL import Image

from univis.domain.policy_episode import CameraStream

OBSERVATIONS = "observations"
IMAGES = "images"
GEOMAP = "geomap"
MASK = "mask"
QPOS = "qpos"
ACTION = "action"
LANGUAGE_PROMPT = "language_prompt"
CHUNKS = "chunks"
SCALE_FACTOR = 4e3
FAR_CLIP = 4.0


class CompressedHDF5Schema:
    """Pure schema operations matching dexechain compressed HDF5 layout."""

    @staticmethod
    def chunk_name(camera_key: str, suffix: str) -> str:
        """Build dexechain chunk side-table dataset names."""

        return f"{camera_key}_{suffix}"

    @staticmethod
    def split_indices(num_frames: int, chunk_count: int) -> list[np.ndarray]:
        """Split frame indices exactly as dexechain's `np.array_split` path."""

        count = max(1, int(chunk_count))
        return [part.astype(np.int64) for part in np.array_split(np.arange(num_frames), count)]

    @staticmethod
    def to_bhw(data: np.ndarray) -> np.ndarray:
        """Convert `(B,H,W,C)` image/video data to dexechain `(B,H,W*C)`."""

        arr = np.asarray(data)
        if arr.ndim == 4:
            frames, height, width, channels = arr.shape
            return arr.reshape(frames, height, width * channels)
        if arr.ndim == 3:
            return arr
        raise ValueError(f"unsupported video shape: {arr.shape}")

    @staticmethod
    def to_bhwc(data: np.ndarray, channels: int = 3) -> np.ndarray:
        """Convert dexechain flattened video chunks back to `(B,H,W,C)`."""

        arr = np.asarray(data)
        if arr.ndim == 4:
            return arr
        if arr.ndim == 3:
            frames, height, width = arr.shape
            return arr.reshape(frames, height, width // channels, channels)
        raise ValueError(f"unsupported video shape: {arr.shape}")

    @staticmethod
    def uint16_depth(data: np.ndarray) -> np.ndarray:
        """Quantize float depth/geomap values using dexechain constants."""

        return np.clip(data * SCALE_FACTOR, 0, FAR_CLIP * SCALE_FACTOR).astype(np.uint16)

    @staticmethod
    def float32_depth(data: np.ndarray) -> np.ndarray:
        """Restore dexechain uint16 depth/geomap chunks to float32 meters."""

        return np.asarray(data, dtype=np.float32) / SCALE_FACTOR

    @staticmethod
    def camera_keys(images_group: h5py.Group) -> list[str]:
        """Return camera groups from a strict compressed HDF5 images group."""

        return [
            key
            for key, node in images_group.items()
            if isinstance(node, h5py.Group) and not key.endswith(("_index", "_start"))
        ]

    @staticmethod
    def camera_streams(images_group: h5py.Group) -> list[CameraStream]:
        """Infer camera metadata from the first chunk of each camera group."""

        streams: list[CameraStream] = []
        for key in CompressedHDF5Schema.camera_keys(images_group):
            height, width = CompressedHDF5Schema._camera_hw(images_group[key])
            streams.append(CameraStream(key=key, label=key, width=width, height=height))
        return streams

    @staticmethod
    def read_image_frame(images_group: h5py.Group, camera_key: str, frame_index: int) -> np.ndarray:
        """Read one BGR frame from dexechain compressed chunk storage."""

        CompressedHDF5Schema.require_camera(images_group, camera_key)
        chunk_id = CompressedHDF5Schema._chunk_id(images_group, camera_key, frame_index)
        chunk = CompressedHDF5Schema.to_bhwc(np.asarray(images_group[camera_key][str(chunk_id)][:]))
        local = int(frame_index) - CompressedHDF5Schema._chunk_start(images_group, camera_key, chunk_id)
        return chunk[max(0, min(local, chunk.shape[0] - 1))]

    @staticmethod
    def encode_frame_png(frame: np.ndarray) -> bytes:
        """Encode one BGR frame as browser-displayable PNG bytes."""

        arr = np.asarray(frame)
        if arr.dtype != np.uint8:
            arr = np.clip(arr, 0, 255).astype(np.uint8)
        if arr.ndim == 3 and arr.shape[2] == 3:
            arr = arr[:, :, ::-1]
        buffer = BytesIO()
        Image.fromarray(arr).save(buffer, format="PNG")
        return buffer.getvalue()

    @staticmethod
    def require_file(root: h5py.File) -> None:
        """Validate the policy episode subset required by UniVis."""

        if OBSERVATIONS not in root or QPOS not in root[OBSERVATIONS]:
            raise ValueError("compressed HDF5 requires observations/qpos")
        if ACTION not in root:
            raise ValueError("compressed HDF5 requires action")
        if CHUNKS not in root:
            raise ValueError("compressed HDF5 requires chunks")
        if IMAGES not in root[OBSERVATIONS]:
            raise ValueError("compressed HDF5 requires observations/images")
        images = root[OBSERVATIONS][IMAGES]
        if not CompressedHDF5Schema.camera_keys(images):
            raise ValueError("compressed HDF5 requires at least one camera group")
        for camera_key in CompressedHDF5Schema.camera_keys(images):
            CompressedHDF5Schema.require_camera(images, camera_key)

    @staticmethod
    def require_camera(images_group: h5py.Group, camera_key: str) -> None:
        """Validate one camera's chunk group and side tables."""

        index_key = CompressedHDF5Schema.chunk_name(camera_key, "index")
        start_key = CompressedHDF5Schema.chunk_name(camera_key, "start")
        if camera_key not in images_group or not isinstance(images_group[camera_key], h5py.Group):
            raise KeyError(f"camera group not found: {camera_key}")
        if index_key not in images_group or start_key not in images_group:
            raise ValueError(f"camera {camera_key} missing index/start datasets")
        if not images_group[camera_key].keys():
            raise ValueError(f"camera {camera_key} has no chunks")

    @staticmethod
    def _camera_hw(camera_group: h5py.Group) -> tuple[int, int]:
        first_key = sorted(camera_group.keys(), key=lambda value: int(value))[0]
        shape = camera_group[first_key].shape
        if len(shape) == 4:
            return int(shape[1]), int(shape[2])
        if len(shape) == 3:
            return int(shape[1]), int(shape[2] // 3)
        raise ValueError(f"unsupported image chunk shape: {shape}")

    @staticmethod
    def _chunk_id(images_group: h5py.Group, camera_key: str, frame_index: int) -> int:
        index = np.asarray(images_group[CompressedHDF5Schema.chunk_name(camera_key, "index")][:])
        frame = max(0, min(int(frame_index), index.shape[0] - 1))
        return int(index[frame])

    @staticmethod
    def _chunk_start(images_group: h5py.Group, camera_key: str, chunk_id: int) -> int:
        starts = np.asarray(images_group[CompressedHDF5Schema.chunk_name(camera_key, "start")][:])
        chunk = max(0, min(int(chunk_id), starts.shape[0] - 1))
        return int(starts[chunk])
