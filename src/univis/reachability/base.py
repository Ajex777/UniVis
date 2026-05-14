"""Base classes for PolicyEpisode reachability checks."""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel

from univis.core.components import ComponentInfo
from univis.domain.policy_episode import PolicyEpisode, ReachabilityOverlay


class ReachabilityReport(BaseModel):
    """Reachability result for one PolicyEpisode.

    Inputs:
        episode_id: Checked episode id.
        backend_name: Component name that produced this result.
        overlay: Per-frame reachability hints for visualization.
        summary: Lightweight numeric/string summary.
    Output:
        Serializable report consumed by API and UI overlays.
    """

    episode_id: str
    backend_name: str
    overlay: ReachabilityOverlay
    summary: dict[str, int | float | str]


class ReachabilityBackend(ABC):
    """Abstract backend for frame-level reachability overlays.

    Inputs:
        Concrete implementations can wrap external IK, custom IK, or mock
        logic, but must accept a `PolicyEpisode`.
    Output:
        A `ReachabilityReport` that does not mutate review status.
    """

    @classmethod
    @abstractmethod
    def info(cls) -> ComponentInfo:
        """Return backend metadata.

        Inputs:
            None.
        Output:
            Component metadata used by registries and diagnostics.
        """

    @abstractmethod
    def evaluate(self, episode: PolicyEpisode) -> ReachabilityReport:
        """Evaluate one episode.

        Inputs:
            episode: Synchronized episode in memory.
        Output:
            Reachability report with per-frame overlay.
        """
