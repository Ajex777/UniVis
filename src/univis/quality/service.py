"""Shared quality-service orchestration for API and CLI entrypoints."""

from __future__ import annotations

from typing import Any

from univis.core.episode_session import EpisodeSession
from univis.domain.policy_episode import PolicyEpisode
from univis.quality.base import (
    PairwiseQualityBackend,
    QualityBackend,
    ReferenceBatchQualityBackend,
    SingleEpisodeQualityBackend,
)


class QualityService:
    """Run registered quality backends against the active episode source."""

    def __init__(
        self,
        session: EpisodeSession,
        backends: list[QualityBackend],
    ) -> None:
        """Initialize quality dependencies.

        Inputs:
            session: Active-source episode session shared with API or CLI.
            backends: Registered quality backends.
        Output:
            Service that exposes GUI/CLI-equivalent quality operations.
        """

        self.session = session
        self.backends = {backend.info().name: backend for backend in backends}

    def compare(
        self,
        current_episode_id: str,
        reference_episode_id: str,
        backend_name: str,
    ) -> Any:
        """Compare one active-source episode with one reference episode."""

        backend = self._backend(backend_name)
        if not isinstance(backend, PairwiseQualityBackend):
            raise TypeError(f"backend {backend_name} does not support pairwise comparison")
        current = self.session.get_episode(current_episode_id)
        reference = self.session.get_episode(reference_episode_id)
        return backend.compare(current, reference)

    def selected_stats(
        self,
        reference_episode_id: str,
        episode_ids: list[str],
        backend_name: str,
    ) -> Any:
        """Aggregate selected episodes against one reference episode."""

        backend = self._backend(backend_name)
        if not isinstance(backend, ReferenceBatchQualityBackend):
            raise TypeError(f"backend {backend_name} does not support selected stats")
        reference = self.session.get_episode(reference_episode_id)
        filtered_ids = [
            episode_id
            for episode_id in episode_ids
            if episode_id != reference_episode_id
        ]
        episodes = [self.session.get_episode(episode_id) for episode_id in filtered_ids]
        return backend.selected_stats(episodes, reference)

    def assess_episode(self, episode_id: str, backend_name: str) -> Any:
        """Run a reference-free check for one active-source episode."""

        backend = self._backend(backend_name)
        if not isinstance(backend, SingleEpisodeQualityBackend):
            raise TypeError(f"backend {backend_name} does not support single-episode assessment")
        episode = self.session.get_episode(episode_id)
        return backend.assess(episode)

    def load_episode(self, episode_id: str) -> PolicyEpisode:
        """Load one episode from the active source for auxiliary consumers."""

        return self.session.get_episode(episode_id)

    def list_episode_ids(self) -> list[str]:
        """Return active-source episode ids in adapter order."""

        return [item["episode_id"] for item in self.session.list_episodes()]

    def _backend(self, name: str) -> QualityBackend:
        """Return a registered quality backend by name."""

        if name not in self.backends:
            raise KeyError(f"unknown quality backend: {name}")
        return self.backends[name]
