"""Shared quality-service orchestration for API and CLI entrypoints."""

from __future__ import annotations

from univis.core.episode_session import EpisodeSession
from univis.domain.policy_episode import PolicyEpisode
from univis.quality.base import TrajectoryQualityBackend
from univis.quality.models import EpisodeDTWComparison, SelectedEpisodeDTWStats


class QualityService:
    """Run registered quality backends against the active episode source."""

    def __init__(
        self,
        session: EpisodeSession,
        backends: list[TrajectoryQualityBackend],
    ) -> None:
        """Initialize quality dependencies.

        Inputs:
            session: Active-source episode session shared with API or CLI.
            backends: Registered trajectory quality backends.
        Output:
            Service that exposes GUI/CLI-equivalent quality operations.
        """

        self.session = session
        self.backends = {backend.info().name: backend for backend in backends}

    def compare_dtw(
        self,
        current_episode_id: str,
        reference_episode_id: str,
        backend_name: str = "DTWTrajectoryQualityBackend",
    ) -> EpisodeDTWComparison:
        """Compare one active-source episode with one reference episode.

        Inputs:
            current_episode_id: Episode id to evaluate.
            reference_episode_id: Expert/reference episode id.
            backend_name: Registered DTW backend name.
        Output:
            Serializable DTW comparison matching the GUI API response.
        """

        backend = self._backend(backend_name)
        current = self.session.get_episode(current_episode_id)
        reference = self.session.get_episode(reference_episode_id)
        return backend.compare(current, reference)

    def selected_stats(
        self,
        reference_episode_id: str,
        episode_ids: list[str],
        backend_name: str = "DTWTrajectoryQualityBackend",
    ) -> SelectedEpisodeDTWStats:
        """Aggregate selected episodes against one reference episode.

        Inputs:
            reference_episode_id: Expert/reference episode id.
            episode_ids: Episode ids to compare one-by-one against reference.
            backend_name: Registered DTW backend name.
        Output:
            Serializable stats payload matching the GUI API response.
        """

        backend = self._backend(backend_name)
        reference = self.session.get_episode(reference_episode_id)
        filtered_ids = [
            episode_id
            for episode_id in episode_ids
            if episode_id != reference_episode_id
        ]
        episodes = [self.session.get_episode(episode_id) for episode_id in filtered_ids]
        return backend.selected_stats(episodes, reference)

    def load_episode(self, episode_id: str) -> PolicyEpisode:
        """Load one episode from the active source for auxiliary consumers.

        Inputs:
            episode_id: Active-source episode id.
        Output:
            Loaded PolicyEpisode, usually for CLI visualization.
        """

        return self.session.get_episode(episode_id)

    def list_episode_ids(self) -> list[str]:
        """Return active-source episode ids in adapter order.

        Inputs:
            None.
        Output:
            Episode id list from the currently selected source.
        """

        return [item["episode_id"] for item in self.session.list_episodes()]

    def _backend(self, name: str) -> TrajectoryQualityBackend:
        """Return a registered quality backend by name."""

        if name not in self.backends:
            raise KeyError(f"unknown quality backend: {name}")
        return self.backends[name]
