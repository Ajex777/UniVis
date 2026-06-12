"""Base contracts for pluggable quality backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from univis.core.components import ComponentInfo
from univis.domain.policy_episode import PolicyEpisode


class QualityBackend(ABC):
    """Abstract root for PolicyEpisode quality checks.

    Inputs:
        Concrete implementations receive one or more `PolicyEpisode` objects.
    Output:
        Serializable report models. Quality checks should not mutate episodes.
    """

    @classmethod
    @abstractmethod
    def info(cls) -> ComponentInfo:
        """Return backend metadata for API registry payloads."""


class PairwiseQualityBackend(QualityBackend):
    """Backend capability for comparing one episode against a reference."""

    @abstractmethod
    def compare(self, current: PolicyEpisode, reference: PolicyEpisode) -> Any:
        """Compare one current episode against a reference episode."""


class ReferenceBatchQualityBackend(QualityBackend):
    """Backend capability for aggregating episodes against one reference."""

    @abstractmethod
    def selected_stats(self, episodes: list[PolicyEpisode], reference: PolicyEpisode) -> Any:
        """Aggregate selected episode metrics against one reference."""


class SingleEpisodeQualityBackend(QualityBackend):
    """Backend capability for reference-free single-episode checks."""

    @abstractmethod
    def assess(self, episode: PolicyEpisode) -> Any:
        """Assess one episode without a reference episode."""
