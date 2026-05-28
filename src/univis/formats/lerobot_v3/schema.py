"""LeRobot v3.0 dataset schema helpers."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import av
import numpy as np
import pyarrow.parquet as pq
from PIL import Image

from univis.domain.policy_episode import CameraStream

META_DIR = "meta"
DATA_DIR = "data"
VIDEOS_DIR = "videos"
INFO_FILE = "info.json"
EPISODES_DIR = "episodes"
STATE_KEY = "observation.state"
STATE_DIM = 10
QPOS_DIM = 20
ACTION_KEY = "action"
CAM_LEFT_WRIST = "cam_left_wrist"
CAM_RIGHT_WRIST = "cam_right_wrist"

# black 640×480 JPEG (pre-encoded for fast serving)
_BLACK_JPEG: bytes | None = None


def _make_black_jpeg(width: int = 640, height: int = 480) -> bytes:
    """Return a single-pixel-expandable black JPEG at the given size."""

    global _BLACK_JPEG
    if _BLACK_JPEG is not None:
        return _BLACK_JPEG
    buf = BytesIO()
    Image.new("RGB", (2, 2), (0, 0, 0)).save(buf, format="JPEG", quality=85)
    _BLACK_JPEG = buf.getvalue()
    return _BLACK_JPEG


class LeRobotV3Schema:
    """Read LeRobot v3.0 dataset directories."""

    @staticmethod
    def load_info(root: Path) -> dict:
        """Load meta/info.json as a dict."""

        import json

        path = root / META_DIR / INFO_FILE
        if not path.exists():
            raise FileNotFoundError(f"missing {INFO_FILE} in {root / META_DIR}")
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def load_episode_records(root: Path) -> list[dict]:
        """Load per-episode metadata rows from meta/episodes parquet files."""

        episodes_dir = root / META_DIR / EPISODES_DIR
        if not episodes_dir.exists():
            raise FileNotFoundError(f"missing {EPISODES_DIR} in {root / META_DIR}")
        records: list[dict] = []
        for pq_path in sorted(episodes_dir.glob("chunk-*/file-*.parquet")):
            records.extend(pq.read_table(pq_path).to_pylist())
        records.sort(key=lambda rec: int(rec["episode_index"]))
        return records

    @staticmethod
    def camera_keys(info: dict) -> list[str]:
        """Return video feature keys from info.json."""

        return [
            key
            for key, ft in info.get("features", {}).items()
            if ft.get("dtype") == "video"
        ]

    @staticmethod
    def camera_streams(info: dict) -> list[CameraStream]:
        """Return two wrist cameras: a synthetic black left wrist and the
        real right wrist from the dataset's video features.

        The left camera always returns black frames; the right camera is
        backed by the first video feature in info.json.
        """

        video_keys = LeRobotV3Schema.camera_keys(info)
        if video_keys:
            ft = info["features"][video_keys[0]]
            shape = ft.get("shape", [480, 640, 3])
            height, width = int(shape[0]), int(shape[1])
        else:
            width, height = 640, 480
        return [
            CameraStream(key=CAM_RIGHT_WRIST, label="Right Wrist", width=width, height=height),
            CameraStream(key=CAM_LEFT_WRIST, label="Left Wrist", width=width, height=height),
        ]

    @staticmethod
    def read_episode_action(root: Path, record: dict) -> np.ndarray:
        """Read action rows for one episode from the data parquet.

        Returns a float32 array shaped (num_frames, 10).
        """

        chunk_idx = int(record["data/chunk_index"])
        file_idx = int(record["data/file_index"])
        start = int(record["dataset_from_index"])
        stop = int(record["dataset_to_index"])
        data_path = root / DATA_DIR / f"chunk-{chunk_idx:03d}" / f"file-{file_idx:03d}.parquet"
        if not data_path.exists():
            raise FileNotFoundError(f"data parquet not found: {data_path}")
        table = pq.read_table(data_path)
        slice_table = table.slice(start, stop - start)
        col = slice_table.column(ACTION_KEY)
        rows = col.combine_chunks().to_pylist()
        return np.asarray(rows, dtype=np.float32)

    @staticmethod
    def read_timestamps(root: Path, record: dict) -> np.ndarray:
        """Read timestamp column for one episode."""

        chunk_idx = int(record["data/chunk_index"])
        file_idx = int(record["data/file_index"])
        start = int(record["dataset_from_index"])
        stop = int(record["dataset_to_index"])
        data_path = root / DATA_DIR / f"chunk-{chunk_idx:03d}" / f"file-{file_idx:03d}.parquet"
        table = pq.read_table(data_path)
        slice_table = table.slice(start, stop - start)
        return np.asarray(slice_table.column("timestamp").combine_chunks().to_pylist(), dtype=np.float32)

    @staticmethod
    def extract_episode_frames(
        root: Path,
        record: dict,
        camera_key: str,
        fps: float,
    ) -> list[tuple[bytes, str]]:
        """Decode all frames for one episode as JPEG bytes.

        Uses ffmpeg to extract the episode's video segment into MJPEG frames
        piped to stdout.  This is a one-time batch operation; the result should
        be cached by the caller.

        Returns a list of (jpeg_bytes, "image/jpeg") tuples.
        """

        import subprocess

        video_chunk_key = f"videos/{camera_key}/chunk_index"
        video_file_key = f"videos/{camera_key}/file_index"
        from_key = f"videos/{camera_key}/from_timestamp"
        to_key = f"videos/{camera_key}/to_timestamp"
        chunk_idx = int(record[video_chunk_key])
        file_idx = int(record[video_file_key])
        start_ts = float(record[from_key])
        end_ts = float(record[to_key])
        duration = max(0.1, end_ts - start_ts)
        video_path = (
            root
            / VIDEOS_DIR
            / camera_key
            / f"chunk-{chunk_idx:03d}"
            / f"file-{file_idx:03d}.mp4"
        )
        if not video_path.exists():
            raise FileNotFoundError(f"video not found: {video_path}")

        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "error",
            "-ss", f"{start_ts:.6f}",
            "-i", str(video_path),
            "-t", f"{duration:.6f}",
            "-vf", f"fps={fps:.6f}",
            "-f", "image2pipe",
            "-c:v", "mjpeg",
            "-q:v", "3",
            "-",
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=60)
        if result.returncode != 0:
            raise RuntimeError(
                f"ffmpeg failed for episode {record.get('episode_index', '?')}: "
                f"{result.stderr.decode('utf-8', errors='replace')[:200]}"
            )
        # Split MJPEG stream into individual JPEG frames
        # MJPEG in image2pipe is just concatenated JPEGs
        raw = result.stdout
        frames: list[tuple[bytes, str]] = []
        pos = 0
        soi = b"\xff\xd8"
        eoi = b"\xff\xd9"
        while pos < len(raw):
            start = raw.find(soi, pos)
            if start == -1:
                break
            end = raw.find(eoi, start + 2)
            if end == -1:
                break
            jpeg_data = raw[start:end + 2]
            frames.append((jpeg_data, "image/jpeg"))
            pos = end + 2
        return frames

    @staticmethod
    def require_root(root: Path) -> dict:
        """Validate a v3 dataset root and return info dict."""

        info = LeRobotV3Schema.load_info(root)
        version = info.get("codebase_version", "unknown")
        if version not in ("v3.0", "3.0"):
            raise ValueError(f"expected LeRobot v3.0 codebase_version, got {version}")
        episodes_dir = root / META_DIR / EPISODES_DIR
        if not episodes_dir.exists():
            raise FileNotFoundError(f"missing {EPISODES_DIR}")
        return info

    @staticmethod
    def action_to_qpos(action: np.ndarray) -> np.ndarray:
        """Map single-arm 10D action to dual-arm 20D qpos.

        The left arm is filled with zero translation, identity rot6d,
        and gripper 1.0.  The right arm carries the dataset action.
        """

        arr = np.asarray(action, dtype=np.float32)
        if arr.ndim == 1:
            arr = arr.reshape(1, -1)
        if arr.ndim != 2 or arr.shape[1] < STATE_DIM:
            raise ValueError(f"expected action shape (N, >=10), got {arr.shape}")
        n = arr.shape[0]
        left = np.zeros((n, STATE_DIM), dtype=np.float32)
        left[:, 3] = 1.0   # rot6d identity row 0, col 0
        left[:, 7] = 1.0   # rot6d identity row 1, col 1
        left[:, 9] = 1.0   # gripper
        return np.concatenate([left, arr[:, :STATE_DIM]], axis=1).astype(np.float32)
