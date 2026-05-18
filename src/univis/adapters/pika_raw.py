"""PIKA raw-data adapter for PolicyEpisode visualization."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from univis.adapters.base import EpisodeSource, ImageFrame, RawEpisodeAdapter, SourceValidation
from univis.adapters.pika_manifest import (
    CAM_LEFT_WRIST,
    CAM_RIGHT_WRIST,
    collect_pika_episode_dirs,
    load_annotation,
    scan_pika_episode,
    write_annotation,
)
from univis.adapters.pika_sync import PikaEpisodeSynchronizer, PikaSyncOptions, PikaSyncResult
from univis.core.components import ComponentInfo
from univis.domain.policy_episode import (
    Annotation,
    ArmFrame,
    CameraStream,
    PolicyEpisode,
    PolicyEpisodeMetadata,
    PolicyFrame,
)
from univis.utils.image_files import image_size, serve_image_file
from univis.utils.hdf5_episode import QPOS_DIM


class PikaRawEpisodeAdapter(RawEpisodeAdapter):
    """Expose PIKA raw episode folders as synchronized PolicyEpisode objects."""

    def __init__(self, options: PikaSyncOptions | None = None) -> None:
        """Initialize a PIKA adapter.

        Inputs:
            options: Synchronization options matching the legacy converter.
        Output:
            Adapter with a small in-process synchronization cache.
        """

        self.synchronizer = PikaEpisodeSynchronizer(options)
        self._cache: dict[Path, PikaSyncResult] = {}

    def clear_caches(self) -> None:
        """Drop sync and chunk caches when switching source."""

        self._cache.clear()

    @classmethod
    def info(cls) -> ComponentInfo:
        """Return adapter metadata for registry and UI display."""

        return ComponentInfo(
            name="PikaRawEpisodeAdapter",
            label="PIKA Raw",
            description="Reads PIKA raw folders into synchronized PolicyEpisode objects.",
            capabilities={
                "source": {
                    "directory_upload": "recursive",
                    "supports_file_upload": False,
                },
            },
        )

    def list_metadata(self, source: EpisodeSource | None = None) -> list[PolicyEpisodeMetadata]:
        """List loadable PIKA raw episodes from a source."""

        metadata: list[PolicyEpisodeMetadata] = []
        for path in self._episode_dirs(source):
            try:
                metadata.append(self._metadata_for_path(path))
            except Exception:
                continue
        return metadata

    def validate_source(self, source: EpisodeSource | None = None) -> SourceValidation:
        """Validate a PIKA raw root or single episode directory."""

        try:
            episode_dirs = self._episode_dirs(source)
            metadata = self.list_metadata(source)
        except Exception as exc:
            return SourceValidation(valid=False, message=str(exc), episode_count=0)
        if not episode_dirs:
            return SourceValidation(valid=False, message="no PIKA raw episode found")
        if not metadata:
            return SourceValidation(
                valid=False,
                message="PIKA episodes found, but none passed synchronization",
                episode_count=0,
            )
        return SourceValidation(
            valid=True,
            message=f"found {len(metadata)} synchronized PIKA episode(s)",
            episode_count=len(metadata),
        )

    def load_episode(
        self,
        episode_id: str,
        source: EpisodeSource | None = None,
    ) -> PolicyEpisode:
        """Load one synchronized PIKA raw episode."""

        path = self.path_for_episode(episode_id, source)
        result = self._sync(path)
        metadata = self._metadata_for_path(path, result)
        return PolicyEpisode(metadata=metadata, frames=self._frames_from_qpos(result))

    def get_image_frame(
        self,
        episode_id: str,
        camera_key: str,
        frame_index: int,
        source: EpisodeSource | None = None,
    ) -> ImageFrame:
        """Return one preview frame, preserving original image format."""

        path = self.path_for_episode(episode_id, source)
        result = self._sync(path)
        if camera_key not in result.image_paths:
            raise KeyError(f"camera not found: {camera_key}")
        paths = result.image_paths[camera_key]
        idx = max(0, min(int(frame_index), len(paths) - 1))
        data, media_type = serve_image_file(paths[idx])
        return ImageFrame(data=data, media_type=media_type)

    def update_annotation(
        self,
        episode_id: str,
        annotation: Annotation,
        source: EpisodeSource | None = None,
    ) -> Annotation:
        """Write annotation text back to `instructions.json`."""

        path = self.path_for_episode(episode_id, source)
        write_annotation(path, annotation)
        return self._metadata_for_path(path).annotation

    def path_for_episode(self, episode_id: str, source: EpisodeSource | None) -> Path:
        """Resolve a stable episode id to a raw episode directory."""

        for path in self._episode_dirs(source):
            if episode_id == path.name:
                return path
        raise KeyError(f"episode not found: {episode_id}")

    def _episode_dirs(self, source: EpisodeSource | None) -> list[Path]:
        """Return naturally sorted raw episode directories from a source."""

        if source is None or source.root_path is None:
            raise ValueError("PikaRawEpisodeAdapter requires source.root_path")
        return collect_pika_episode_dirs(source.root_path)

    def _metadata_for_path(
        self,
        path: Path,
        result: PikaSyncResult | None = None,
    ) -> PolicyEpisodeMetadata:
        """Build metadata for a synchronized raw episode."""

        sync = result or self._sync(path)
        return PolicyEpisodeMetadata(
            episode_id=path.name,
            title=path.name,
            num_frames=int(sync.qpos.shape[0]),
            fps=self._fps(sync.timestamps),
            cameras=self._cameras(sync),
            annotation=load_annotation(path),
        )

    def _sync(self, path: Path) -> PikaSyncResult:
        """Synchronize and cache one raw episode directory."""

        episode_dir = Path(path).expanduser().resolve()
        if episode_dir not in self._cache:
            self._cache[episode_dir] = self.synchronizer.synchronize(scan_pika_episode(episode_dir))
        return self._cache[episode_dir]

    def _frames_from_qpos(self, result: PikaSyncResult) -> list[PolicyFrame]:
        """Convert synchronized qpos rows to PolicyFrame objects."""

        qpos = np.asarray(result.qpos, dtype=np.float32)
        if qpos.ndim != 2 or qpos.shape[1] < QPOS_DIM:
            raise ValueError(f"expected qpos shape (N, >=20), got {qpos.shape}")
        frames: list[PolicyFrame] = []
        for index, row in enumerate(qpos[:, :QPOS_DIM]):
            frames.append(
                PolicyFrame(
                    index=index,
                    timestamp=float(result.timestamps[index]),
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

    def _cameras(self, result: PikaSyncResult) -> list[CameraStream]:
        """Infer fixed PIKA wrist camera metadata from synchronized image paths."""

        labels = {CAM_LEFT_WRIST: "Left Wrist", CAM_RIGHT_WRIST: "Right Wrist"}
        cameras: list[CameraStream] = []
        for key in (CAM_LEFT_WRIST, CAM_RIGHT_WRIST):
            paths = result.image_paths.get(key, [])
            width, height = image_size(paths[0]) if paths else (640, 360)
            cameras.append(CameraStream(key=key, label=labels[key], width=width, height=height))
        return cameras

    def _fps(self, timestamps: np.ndarray) -> float:
        """Estimate playback FPS from synchronized timestamps."""

        if timestamps.shape[0] < 2:
            return 12.0
        diffs = np.diff(timestamps)
        positive = diffs[diffs > 1e-6]
        return float(1.0 / np.median(positive)) if positive.size else 12.0
