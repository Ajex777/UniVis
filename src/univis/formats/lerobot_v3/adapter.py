"""Adapter for LeRobot v3.0 datasets."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from univis.adapters.base import EpisodeSource, ImageFrame, RawEpisodeAdapter, SourceValidation
from univis.core.components import ComponentInfo
from univis.domain.policy_episode import (
    Annotation,
    ArmFrame,
    CameraStream,
    PolicyEpisode,
    PolicyEpisodeMetadata,
    PolicyFrame,
)
from univis.formats.lerobot_v3.schema import (
    CAM_LEFT_WRIST,
    CAM_RIGHT_WRIST,
    STATE_DIM,
    LeRobotV3Schema,
    _make_black_jpeg,
)
from univis.utils.sorting import natural_sort_key


class LeRobotV3EpisodeAdapter(RawEpisodeAdapter):
    """Expose LeRobot v3.0 datasets as PolicyEpisode objects."""

    def __init__(self) -> None:
        """Initialize with in-memory caches for frames, records, and info."""

        self._frame_cache: dict[str, dict[int, tuple[bytes, str]]] = {}
        self._records_cache: dict[str, list[dict]] = {}
        self._info_cache: dict[str, dict] = {}

    def clear_caches(self) -> None:
        """Drop all caches when switching source."""

        self._frame_cache.clear()
        self._records_cache.clear()
        self._info_cache.clear()

    @classmethod
    def info(cls) -> ComponentInfo:
        """Return adapter metadata for registry and UI display."""

        return ComponentInfo(
            name="LeRobotV3EpisodeAdapter",
            label="LeRobot v3",
            description="Reads LeRobot v3.0 datasets into PolicyEpisode objects.",
            capabilities={
                "source": {
                    "directory_upload": "recursive",
                    "supports_file_upload": False,
                },
                "conversion": {"default_status": "pending", "default_progress": 0.0},
            },
        )

    def list_metadata(self, source: EpisodeSource | None = None) -> list[PolicyEpisodeMetadata]:
        """List episodes from a LeRobot v3 dataset root."""

        root = self._resolve_root(source)
        info = self._load_info_cached(root)
        records = self._load_records_cached(root)
        fps = float(info.get("fps", 30.0))
        cameras = LeRobotV3Schema.camera_streams(info)
        return [self._rec_to_metadata(rec, fps, cameras) for rec in records]

    def validate_source(self, source: EpisodeSource | None = None) -> SourceValidation:
        """Validate a LeRobot v3 dataset root."""

        try:
            root = self._resolve_root(source)
            LeRobotV3Schema.require_root(root)
            records = self._load_records_cached(root)
            return SourceValidation(
                valid=True,
                message=f"found {len(records)} episode(s) in LeRobot v3 dataset",
                episode_count=len(records),
            )
        except Exception as exc:
            return SourceValidation(valid=False, message=str(exc))

    def load_episode(
        self, episode_id: str, source: EpisodeSource | None = None,
    ) -> PolicyEpisode:
        """Load one LeRobot v3 episode. Uses ``action`` for the right arm;
        left arm is identity (zero xyz, identity rot6d, gripper 1.0)."""

        root = self._resolve_root(source)
        rec = self._record_for_episode(root, episode_id)
        info = self._load_info_cached(root)
        fps = float(info.get("fps", 30.0))
        action = LeRobotV3Schema.read_episode_action(root, rec)
        timestamps = LeRobotV3Schema.read_timestamps(root, rec)
        qpos = LeRobotV3Schema.action_to_qpos(action)
        metadata = self._rec_to_metadata(rec, fps, LeRobotV3Schema.camera_streams(info))
        return PolicyEpisode(metadata=metadata, frames=self._qpos_to_frames(qpos, timestamps))

    def get_image_frame(
        self, episode_id: str, camera_key: str, frame_index: int,
        source: EpisodeSource | None = None,
    ) -> ImageFrame:
        """Return one JPEG frame.  Left wrist = black; right wrist = MP4
        segment batch-decoded via ffmpeg and cached in memory."""

        if camera_key == CAM_LEFT_WRIST:
            return ImageFrame(data=_make_black_jpeg(), media_type="image/jpeg")

        root = self._resolve_root(source)
        rec = self._record_for_episode(root, episode_id)
        info = self._load_info_cached(root)
        fps = float(info.get("fps", 30.0))
        idx = max(0, min(int(frame_index), int(rec["length"]) - 1))

        video_keys = LeRobotV3Schema.camera_keys(info)
        video_key = video_keys[0] if video_keys else "observation.images.cam_0_rgb"
        cache_key = f"{episode_id}:{video_key}"
        if cache_key not in self._frame_cache:
            frames = LeRobotV3Schema.extract_episode_frames(root, rec, video_key, fps)
            self._frame_cache[cache_key] = frames
        data, media_type = self._frame_cache[cache_key][idx]
        return ImageFrame(data=data, media_type=media_type)

    def path_for_episode(self, episode_id: str, source: EpisodeSource | None) -> Path:
        """Resolve the root path — episodes are not per-file in v3."""

        return self._resolve_root(source)

    def update_annotation(
        self, episode_id: str, annotation: Annotation,
        source: EpisodeSource | None = None,
    ) -> Annotation:
        """Write annotation to ``univis_annotations.jsonl`` in the dataset root."""

        root = self._resolve_root(source)
        rec = self._record_for_episode(root, episode_id)
        ep_idx = int(rec["episode_index"])
        sidecar_path = root / "univis_annotations.jsonl"
        records: dict[int, dict] = {}
        if sidecar_path.exists():
            for line in sidecar_path.read_text("utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    item = json.loads(line)
                    records[int(item["episode_index"])] = item
                except (json.JSONDecodeError, KeyError):
                    continue
        records[ep_idx] = {
            "episode_index": ep_idx,
            "language_prompt": annotation.language_prompt,
            "review_status": annotation.review_status,
        }
        lines = [json.dumps(records[k], ensure_ascii=False) for k in sorted(records)]
        sidecar_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return annotation

    def _resolve_root(self, source: EpisodeSource | None) -> Path:
        if source is None or source.root_path is None:
            raise ValueError("LeRobotV3EpisodeAdapter requires source.root_path")
        return source.root_path.expanduser().resolve()

    def _load_info_cached(self, root: Path) -> dict:
        root_str = str(root)
        if root_str not in self._info_cache:
            self._info_cache[root_str] = LeRobotV3Schema.load_info(root)
        return self._info_cache[root_str]

    def _load_records_cached(self, root: Path) -> list[dict]:
        root_str = str(root)
        if root_str not in self._records_cache:
            self._records_cache[root_str] = LeRobotV3Schema.load_episode_records(root)
        return self._records_cache[root_str]

    def _record_for_episode(self, root: Path, episode_id: str) -> dict:
        records = self._load_records_cached(root)
        for rec in records:
            if str(rec["episode_index"]) == episode_id:
                return rec
        raise KeyError(f"episode not found: {episode_id}")

    def _rec_to_metadata(
        self,
        rec: dict,
        fps: float,
        cameras: list[CameraStream],
    ) -> PolicyEpisodeMetadata:
        episode_id = str(rec["episode_index"])
        tasks = rec.get("tasks", [])
        title = tasks[0] if tasks else f"episode {episode_id}"
        return PolicyEpisodeMetadata(
            episode_id=episode_id,
            title=title,
            num_frames=int(rec["length"]),
            fps=fps,
            cameras=cameras,
            annotation=Annotation(language_prompt=""),
        )

    def _qpos_to_frames(
        self,
        qpos: np.ndarray,
        timestamps: np.ndarray,
    ) -> list[PolicyFrame]:
        """Convert 20D qpos rows to PolicyFrame objects."""

        if qpos.ndim != 2 or qpos.shape[1] < STATE_DIM * 2:
            raise ValueError(f"expected qpos shape (N, >=20), got {qpos.shape}")
        frames: list[PolicyFrame] = []
        for index in range(qpos.shape[0]):
            row = qpos[index]
            ts = float(timestamps[index]) if index < len(timestamps) else float(index)
            frames.append(
                PolicyFrame(
                    index=index,
                    timestamp=ts,
                    left=ArmFrame(
                        xyz=row[0:3].astype(float).tolist(),
                        rot6d=row[3:9].astype(float).tolist(),
                        gripper=float(row[9]),
                    ),
                    right=ArmFrame(
                        xyz=row[10:13].astype(float).tolist(),
                        rot6d=row[13:19].astype(float).tolist(),
                        gripper=float(row[19]),
                    ),
                )
            )
        return frames
