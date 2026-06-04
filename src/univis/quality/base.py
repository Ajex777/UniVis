"""Base classes for trajectory quality backends."""

from __future__ import annotations

from abc import ABC, abstractmethod

from univis.core.components import ComponentInfo
from univis.domain.policy_episode import PolicyEpisode
from univis.quality.models import EpisodeDTWComparison, SelectedEpisodeDTWStats


class TrajectoryQualityBackend(ABC):
    """Abstract quality backend for PolicyEpisode trajectory checks.

    Inputs:
        Concrete implementations can compare one episode against a reference
        and aggregate selected episode statistics.
    Output:
        Serializable quality reports that do not mutate annotations.
    """

    @classmethod
    @abstractmethod
    def info(cls) -> ComponentInfo:
        """Return backend metadata for API registry payloads."""

    @abstractmethod
    def compare(
        self,
        current: PolicyEpisode,
        reference: PolicyEpisode,
    ) -> EpisodeDTWComparison:
        """Compare one current episode against a reference episode."""

    @abstractmethod
    def selected_stats(
        self,
        episodes: list[PolicyEpisode],
        reference: PolicyEpisode,
    ) -> SelectedEpisodeDTWStats:
        """Aggregate selected episode metrics against one reference."""

    @abstractmethod
    def choose_medoid(self, episodes: list[PolicyEpisode]) -> str:
        """Choose the most representative episode id from a list."""
