"""Dexforce W1 teleop raw adapter."""

from __future__ import annotations

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
from univis.formats.dexforce_w1_teleop.fk import W1FKBatchResult, W1ForwardKinematics
from univis.formats.dexforce_w1_teleop.manifest import (
    collect_w1_episode_dirs,
    load_annotation,
    scan_w1_episode,
    write_annotation,
)
from univis.formats.dexforce_w1_teleop.settings import W1TeleopConfig
from univis.formats.dexforce_w1_teleop.sync import W1EpisodeSynchronizer, W1SyncResult
from univis.utils.image_files import image_size, serve_image_file


class DexforceW1TeleopAdapter(RawEpisodeAdapter):
    """Expose Dexforce W1 teleop folders as synchronized PolicyEpisode objects."""

    def __init__(
        self,
        config: W1TeleopConfig | None = None,
        fk: W1ForwardKinematics | None = None,
    ) -> None:
        """Initialize W1 adapter with config, synchronizer, and FK helper."""

        self.config = config or W1TeleopConfig.load()
        self.synchronizer = W1EpisodeSynchronizer(self.config)
        self.fk = fk or W1ForwardKinematics(self.config)
        self._cache: dict[Path, W1SyncResult] = {}

    def clear_caches(self) -> None:
        """Clear synchronized episode cache when source changes."""

        self._cache.clear()

    @classmethod
    def info(cls) -> ComponentInfo:
        """Return adapter metadata for registry and UI display."""

        return ComponentInfo(
            name="DexforceW1TeleopAdapter",
            label="Dexforce W1 Teleop",
            aliases=["W1Teleop"],
            description="Reads Dexforce W1 teleop qpos folders with configurable W1 FK.",
            capabilities={
                "source": {
                    "directory_upload": "recursive",
                    "supports_file_upload": False,
                },
                "conversion": {"default_status": "pending", "default_progress": 0.0},
            },
        )

    def list_metadata(self, source: EpisodeSource | None = None) -> list[PolicyEpisodeMetadata]:
        """List W1 teleop episodes without running FK."""

        metadata: list[PolicyEpisodeMetadata] = []
        for path in self._episode_dirs(source):
            try:
                metadata.append(self._metadata_for_path(path))
            except Exception:
                continue
        return metadata

    def validate_source(self, source: EpisodeSource | None = None) -> SourceValidation:
        """Validate a W1 teleop root or single episode directory."""

        try:
            episode_dirs = self._episode_dirs(source)
            metadata = self.list_metadata(source)
        except Exception as exc:
            return SourceValidation(valid=False, message=str(exc), episode_count=0)
        if not episode_dirs:
            return SourceValidation(valid=False, message="no W1 teleop episode found")
        if not metadata:
            return SourceValidation(valid=False, message="W1 episodes found, but none synchronized", episode_count=0)
        return SourceValidation(valid=True, message=f"found {len(metadata)} W1 teleop episode(s)", episode_count=len(metadata))

    def load_episode(
        self,
        episode_id: str,
        source: EpisodeSource | None = None,
    ) -> PolicyEpisode:
        """Load one W1 episode, converting full qpos to dual-arm EEF pose."""

        path = self.path_for_episode(episode_id, source)
        sync = self._sync(path)
        fk_result = self.fk.compute_dual_arm_eef_batch(sync.qpos)
        metadata = self._metadata_for_path(path, sync)
        return PolicyEpisode(metadata=metadata, frames=self._frames(sync, fk_result))

    def get_image_frame(
        self,
        episode_id: str,
        camera_key: str,
        frame_index: int,
        source: EpisodeSource | None = None,
    ) -> ImageFrame:
        """Return one raw W1 image frame."""

        path = self.path_for_episode(episode_id, source)
        sync = self._sync(path)
        if camera_key not in sync.image_paths or not sync.image_paths[camera_key]:
            raise KeyError(f"camera not found or empty: {camera_key}")
        paths = sync.image_paths[camera_key]
        idx = max(0, min(int(frame_index), len(paths) - 1))
        data, media_type = serve_image_file(paths[idx])
        return ImageFrame(data=data, media_type=media_type)

    def update_annotation(
        self,
        episode_id: str,
        annotation: Annotation,
        source: EpisodeSource | None = None,
    ) -> Annotation:
        """Write prompt and review metadata back to the W1 qpos JSON."""

        path = self.path_for_episode(episode_id, source)
        write_annotation(path, annotation, self.config)
        return load_annotation(path, self.config)

    def path_for_episode(self, episode_id: str, source: EpisodeSource | None) -> Path:
        """Resolve episode id to a W1 episode directory."""

        for path in self._episode_dirs(source):
            if episode_id == path.name:
                return path
        raise KeyError(f"episode not found: {episode_id}")

    def _episode_dirs(self, source: EpisodeSource | None) -> list[Path]:
        """Return W1 episode directories from a source."""

        if source is None or source.root_path is None:
            raise ValueError("DexforceW1TeleopAdapter requires source.root_path")
        return collect_w1_episode_dirs(source.root_path, self.config)

    def _metadata_for_path(
        self,
        path: Path,
        sync: W1SyncResult | None = None,
    ) -> PolicyEpisodeMetadata:
        """Build metadata for a synchronized W1 episode."""

        result = sync or self._sync(path)
        return PolicyEpisodeMetadata(
            episode_id=path.name,
            title=path.name,
            num_frames=int(result.qpos.shape[0]),
            fps=self._fps(result.timestamps),
            cameras=self._cameras(result),
            annotation=load_annotation(path, self.config),
        )

    def _sync(self, path: Path) -> W1SyncResult:
        """Synchronize and cache one W1 episode directory."""

        episode_dir = Path(path).expanduser().resolve()
        if episode_dir not in self._cache:
            self._cache[episode_dir] = self.synchronizer.synchronize(
                scan_w1_episode(episode_dir, self.config)
            )
        return self._cache[episode_dir]

    def _frames(self, sync: W1SyncResult, fk_result: W1FKBatchResult) -> list[PolicyFrame]:
        """Convert FK output and grippers into PolicyFrame objects."""

        left_grip = self._gripper(sync.qpos, "left")
        right_grip = self._gripper(sync.qpos, "right")
        frames: list[PolicyFrame] = []
        for index in range(sync.qpos.shape[0]):
            frames.append(
                PolicyFrame(
                    index=index,
                    timestamp=float(sync.timestamps[index]),
                    left=_arm_frame(fk_result.left[index], left_grip[index]),
                    right=_arm_frame(fk_result.right[index], right_grip[index]),
                )
            )
        return frames

    def _gripper(self, qpos: np.ndarray, side: str) -> np.ndarray:
        """Extract and normalize one gripper from full qpos."""

        arm = self.config.left_arm if side == "left" else self.config.right_arm
        idx = self.config.indices_for((arm.gripper_name,))[0]
        min_value, max_value = self.config.gripper_ranges.get(side, (0.0, 1.0))
        if max_value <= min_value:
            raise ValueError(f"invalid {side} gripper range")
        return np.clip((qpos[:, idx] - min_value) / (max_value - min_value), 0.0, 1.0).astype(float)

    def _cameras(self, sync: W1SyncResult) -> list[CameraStream]:
        """Build camera metadata for streams that have frames."""

        cameras: list[CameraStream] = []
        config_by_key = {camera.key: camera for camera in self.config.cameras}
        for key, paths in sync.image_paths.items():
            if not paths:
                continue
            cfg = config_by_key[key]
            width, height = image_size(paths[0])
            cameras.append(CameraStream(key=cfg.key, label=cfg.label, width=width, height=height))
        return cameras

    def _fps(self, timestamps: np.ndarray) -> float:
        """Estimate FPS from synchronized timestamps."""

        if timestamps.shape[0] < 2:
            return 30.0
        diffs = np.diff(timestamps)
        positive = diffs[diffs > 1e-6]
        return float(1.0 / np.median(positive)) if positive.size else 30.0


def _arm_frame(pose9: np.ndarray, gripper: float) -> ArmFrame:
    """Build an ArmFrame from one FK pose row and gripper value."""

    return ArmFrame(
        xyz=pose9[:3].astype(float).tolist(),
        rot6d=pose9[3:9].astype(float).tolist(),
        gripper=float(gripper),
    )
