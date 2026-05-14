"""Fake adapter implementation backed by deterministic PolicyEpisode data."""

from __future__ import annotations

from univis.adapters.base import EpisodeSource, RawEpisodeAdapter
from univis.core.components import ComponentInfo
from univis.data.fake_policy_episode import FakePolicyEpisodeRepository
from univis.domain.policy_episode import PolicyEpisode, PolicyEpisodeMetadata


class FakePolicyEpisodeAdapter(RawEpisodeAdapter):
    """Adapter exposing the Phase 00 fake repository through Phase 01 APIs.

    Inputs:
        repository: In-memory fake episode repository.
    Output:
        Adapter instance that can list and load fake `PolicyEpisode` objects.
    """

    def __init__(self, repository: FakePolicyEpisodeRepository | None = None) -> None:
        """Initialize the fake adapter.

        Inputs:
            repository: Optional repository override for tests.
        Output:
            Adapter with deterministic fake data.
        """

        self.repository = repository or FakePolicyEpisodeRepository()

    @classmethod
    def info(cls) -> ComponentInfo:
        """Return adapter metadata.

        Inputs:
            None.
        Output:
            Component metadata for registry and UI display.
        """

        return ComponentInfo(
            name="FakePolicyEpisodeAdapter",
            label="Fake PolicyEpisode",
            description="In-memory fake data for UI and adapter smoke tests.",
        )

    def list_metadata(self, source: EpisodeSource | None = None) -> list[PolicyEpisodeMetadata]:
        """List fake episode metadata.

        Inputs:
            source: Ignored for fake data.
        Output:
            Metadata for deterministic fake episodes.
        """

        return self.repository.list_metadata()

    def load_episode(
        self,
        episode_id: str,
        source: EpisodeSource | None = None,
    ) -> PolicyEpisode:
        """Load one fake episode.

        Inputs:
            episode_id: Stable fake episode id.
            source: Ignored for fake data.
        Output:
            Complete fake `PolicyEpisode`.
        """

        return self.repository.get_episode(episode_id)
