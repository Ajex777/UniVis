"""Mock reachability backend for Phase 01 validation."""

from __future__ import annotations

from univis.core.components import ComponentInfo
from univis.domain.policy_episode import PolicyEpisode, ReachabilityOverlay
from univis.reachability.base import ReachabilityBackend, ReachabilityReport


class MockReachabilityBackend(ReachabilityBackend):
    """Reachability backend that reuses or synthesizes lightweight overlays.

    Inputs:
        None.
    Output:
        Backend instance for UI smoke tests before real IK integration.
    """

    @classmethod
    def info(cls) -> ComponentInfo:
        """Return backend metadata.

        Inputs:
            None.
        Output:
            Component metadata for registry and diagnostics.
        """

        return ComponentInfo(
            name="MockReachabilityBackend",
            label="Mock Reachability",
            description="Reuses existing overlays or marks all frames reachable.",
        )

    def evaluate(self, episode: PolicyEpisode) -> ReachabilityReport:
        """Evaluate an episode without robot-specific dependencies.

        Inputs:
            episode: Synchronized episode in memory.
        Output:
            Reachability report suitable for trajectory overlay tests.
        """

        overlay = episode.metadata.reachability or ReachabilityOverlay(
            reachable=[True] * episode.metadata.num_frames,
            reasons=[""] * episode.metadata.num_frames,
        )
        unreachable = overlay.reachable.count(False)
        return ReachabilityReport(
            episode_id=episode.metadata.episode_id,
            backend_name=self.info().name,
            overlay=overlay,
            summary={
                "num_frames": episode.metadata.num_frames,
                "unreachable_frames": unreachable,
            },
        )
