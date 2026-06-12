"""PolicyEpisode trajectory extraction helpers for DTW."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from univis.domain.policy_episode import PolicyEpisode


@dataclass(frozen=True)
class DualArmPoseTrajectories:
    """Left and right EEF pose trajectories consumed by DTW comparators."""

    left: np.ndarray
    right: np.ndarray


class DualArmEEFExtractor:
    """Extract left/right xyz + rot6d trajectories from a PolicyEpisode."""

    def extract(self, episode: PolicyEpisode) -> DualArmPoseTrajectories:
        """Return left and right pose arrays for one episode.

        Inputs:
            episode: Synchronized PolicyEpisode.
        Output:
            Dual-arm trajectories with shape `(T, 9)` for each arm.
        """

        left = [
            [*frame.left.xyz, *frame.left.rot6d]
            for frame in episode.frames
        ]
        right = [
            [*frame.right.xyz, *frame.right.rot6d]
            for frame in episode.frames
        ]
        return DualArmPoseTrajectories(
            left=np.asarray(left, dtype=np.float64),
            right=np.asarray(right, dtype=np.float64),
        )
