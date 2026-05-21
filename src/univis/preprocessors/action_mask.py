"""Action masking preprocessor — zeros out arm actions for one side."""

from __future__ import annotations

from univis.core.components import ComponentInfo
from univis.domain.policy_episode import ArmFrame, PolicyEpisode, PolicyFrame
from univis.preprocessors.base import EpisodePreprocessor

_IDENTITY_ROT6D = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0]
_ZERO_XYZ = [0.0, 0.0, 0.0]


class ActionMaskPreprocessor(EpisodePreprocessor):
    """Replace one arm's actions with identity values in exported data."""

    def __init__(self, side: str) -> None:
        self.side = side  # "left" or "right"

    def info(self) -> ComponentInfo:
        return ComponentInfo(
            name=f"mask_{self.side}_action",
            label=f"Mask {self.side.title()} Action",
            description=f"Set {self.side} arm to zero actions in exported data.",
        )

    def preprocess_episode(self, episode: PolicyEpisode) -> PolicyEpisode:
        masked = ArmFrame(xyz=_ZERO_XYZ, rot6d=_IDENTITY_ROT6D, gripper=1.0)
        if self.side == "left":
            frames = [
                PolicyFrame(
                    index=f.index, timestamp=f.timestamp, left=masked, right=f.right
                )
                for f in episode.frames
            ]
        else:
            frames = [
                PolicyFrame(
                    index=f.index, timestamp=f.timestamp, left=f.left, right=masked
                )
                for f in episode.frames
            ]
        return PolicyEpisode(metadata=episode.metadata, frames=frames)
