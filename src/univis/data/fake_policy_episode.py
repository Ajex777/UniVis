"""Fake PolicyEpisode repository for Phase 00 visualization."""

from __future__ import annotations

from dataclasses import dataclass, field

from univis.domain.policy_episode import (
    Annotation,
    ArmFrame,
    CameraStream,
    PolicyEpisode,
    PolicyEpisodeMetadata,
    PolicyFrame,
    ReachabilityOverlay,
)
from univis.utils.geometry import lerp, wave


@dataclass
class FakePolicyEpisodeRepository:
    """In-memory fake episode store used before real adapters exist.

    Inputs:
        None. Episodes are generated deterministically at construction time.
    Output:
        A repository-like object with list, metadata, frame, trajectory, and
        annotation methods used by the API layer.
    """

    episodes: dict[str, PolicyEpisode] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Populate deterministic fake episodes.

        Inputs:
            None.
        Output:
            The repository gains three fake episodes with 1, 2, and 4 cameras.
        """

        if self.episodes:
            return
        self.episodes = {
            "fake-single": self._make_episode("fake-single", 1, 96, "single camera pick"),
            "fake-dual": self._make_episode("fake-dual", 2, 128, "dual wrist handover"),
            "fake-quad": self._make_episode("fake-quad", 4, 144, "multi camera sorting"),
            "fake-rejected": self._make_episode("fake-rejected", 2, 72, "bad lighting sample"),
        }
        self.episodes["fake-rejected"].metadata.annotation.review_status = "rejected"

    def list_metadata(self) -> list[PolicyEpisodeMetadata]:
        """Return metadata for all fake episodes.

        Inputs:
            None.
        Output:
            List of episode metadata sorted by episode id.
        """

        return [self.episodes[key].metadata for key in sorted(self.episodes)]

    def conversion_state(self, episode_id: str) -> dict[str, object]:
        """Return fake conversion state for UI status rendering.

        Inputs:
            episode_id: Stable episode identifier.
        Output:
            Dict containing status and progress in [0, 1].
        """

        status_map = {
            "fake-dual": ("converting", 0.42),
            "fake-quad": ("converted", 1.0),
            "fake-rejected": ("rejected", 0.0),
        }
        status, progress = status_map.get(episode_id, ("pending", 0.0))
        return {"status": status, "progress": float(progress)}

    def get_episode(self, episode_id: str) -> PolicyEpisode:
        """Return one fake episode by id.

        Inputs:
            episode_id: Stable episode identifier.
        Output:
            Complete `PolicyEpisode`.
        Raises:
            KeyError: If episode_id does not exist.
        """

        return self.episodes[episode_id]

    def get_metadata(self, episode_id: str) -> PolicyEpisodeMetadata:
        """Return metadata for one fake episode.

        Inputs:
            episode_id: Stable episode identifier.
        Output:
            Episode metadata without requiring callers to inspect frames.
        """

        return self.get_episode(episode_id).metadata

    def get_frame(self, episode_id: str, frame_index: int) -> PolicyFrame:
        """Return one synchronized policy frame.

        Inputs:
            episode_id: Stable episode identifier.
            frame_index: Local frame index.
        Output:
            A single `PolicyFrame`, clamped to the valid frame range.
        """

        episode = self.get_episode(episode_id)
        idx = max(0, min(int(frame_index), len(episode.frames) - 1))
        return episode.frames[idx]

    def update_annotation(self, episode_id: str, annotation: Annotation) -> Annotation:
        """Update in-memory annotation for one episode.

        Inputs:
            episode_id: Stable episode identifier.
            annotation: Replacement annotation payload.
        Output:
            The saved annotation.
        """

        episode = self.get_episode(episode_id)
        episode.metadata.annotation = annotation
        return episode.metadata.annotation

    def _make_episode(
        self,
        episode_id: str,
        camera_count: int,
        num_frames: int,
        prompt: str,
    ) -> PolicyEpisode:
        """Generate one deterministic fake `PolicyEpisode`.

        Inputs:
            episode_id: Stable fake episode id.
            camera_count: Number of image observation streams.
            num_frames: Number of synchronized frames.
            prompt: Default language prompt.
        Output:
            Complete fake `PolicyEpisode`.
        """

        cameras = self._make_cameras(camera_count)
        frames = [
            self._make_frame(index=idx, num_frames=num_frames)
            for idx in range(num_frames)
        ]
        reachability = self._make_reachability(num_frames)
        metadata = PolicyEpisodeMetadata(
            episode_id=episode_id,
            title=episode_id.replace("-", " ").title(),
            num_frames=num_frames,
            fps=12.0,
            cameras=cameras,
            annotation=Annotation(language_prompt=prompt),
            reachability=reachability,
        )
        return PolicyEpisode(metadata=metadata, frames=frames)

    def _make_cameras(self, camera_count: int) -> list[CameraStream]:
        """Create variable fake camera streams.

        Inputs:
            camera_count: Number of cameras requested.
        Output:
            Camera metadata list with stable keys.
        """

        base = [
            ("head_rgb", "Head RGB", "rgb"),
            ("left_wrist_rgb", "Left Wrist RGB", "rgb"),
            ("right_wrist_rgb", "Right Wrist RGB", "rgb"),
            ("left_wrist_depth", "Left Wrist Depth", "depth"),
        ]
        return [
            CameraStream(key=key, label=label, width=640, height=360, kind=kind)
            for key, label, kind in base[:camera_count]
        ]

    def _make_frame(self, *, index: int, num_frames: int) -> PolicyFrame:
        """Create one dual-arm frame.

        Inputs:
            index: Local frame index.
            num_frames: Episode frame count.
        Output:
            A synchronized `PolicyFrame`.
        """

        t = 0.0 if num_frames <= 1 else index / float(num_frames - 1)
        left_xyz = [lerp(-0.34, -0.10, t), -0.18 + 0.06 * wave(t), 0.30 + 0.08 * t]
        right_xyz = [lerp(0.34, 0.10, t), 0.18 + 0.06 * wave(t, 1.0), 0.32 + 0.05 * t]
        left = ArmFrame(
            xyz=left_xyz,
            rot6d=[1.0, 0.0, 0.0, 0.0, 1.0, 0.0],
            gripper=0.5 + 0.45 * wave(t, 0.3),
        )
        right = ArmFrame(
            xyz=right_xyz,
            rot6d=[1.0, 0.0, 0.0, 0.0, 1.0, 0.0],
            gripper=0.5 + 0.45 * wave(t, 1.7),
        )
        return PolicyFrame(index=index, timestamp=index / 12.0, left=left, right=right)

    def _make_reachability(self, num_frames: int) -> ReachabilityOverlay:
        """Create deterministic reachability hints for fake visualization.

        Inputs:
            num_frames: Episode frame count.
        Output:
            Frame-level fake reachability overlay.
        """

        reachable: list[bool] = []
        reasons: list[str] = []
        for idx in range(num_frames):
            bad = num_frames // 3 <= idx <= num_frames // 3 + 8
            reachable.append(not bad)
            reasons.append("" if not bad else "fake_ik_unreachable")
        return ReachabilityOverlay(reachable=reachable, reasons=reasons)
