"""Base classes for converting external data into PolicyEpisode objects."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from pydantic import BaseModel

from univis.core.components import ComponentInfo
from univis.domain.policy_episode import PolicyEpisode, PolicyEpisodeMetadata


class EpisodeSource(BaseModel):
    """Describes an adapter-readable episode source.

    Inputs:
        root_path: Optional local dataset root path.
        options: Adapter-specific options that should remain UI/API agnostic.
    Output:
        Immutable-ish source request passed from orchestration to adapters.
    """

    root_path: Path | None = None
    options: dict[str, str | int | float | bool] = {}


class RawEpisodeAdapter(ABC):
    """Abstract adapter that exposes external episodes as PolicyEpisode.

    Inputs:
        Concrete implementations can wrap fake data, raw UMI folders, HDF5
        files, or future EEF-pose datasets.
    Output:
        A common interface for listing and loading synchronized episodes.
    """

    @classmethod
    @abstractmethod
    def info(cls) -> ComponentInfo:
        """Return adapter metadata.

        Inputs:
            None.
        Output:
            Component metadata used by registries and UI dropdowns.
        """

    @abstractmethod
    def list_metadata(self, source: EpisodeSource | None = None) -> list[PolicyEpisodeMetadata]:
        """List episodes available from a source.

        Inputs:
            source: Optional data source descriptor.
        Output:
            Metadata for all loadable episodes.
        """

    @abstractmethod
    def load_episode(
        self,
        episode_id: str,
        source: EpisodeSource | None = None,
    ) -> PolicyEpisode:
        """Load one synchronized episode.

        Inputs:
            episode_id: Stable episode identifier from `list_metadata`.
            source: Optional data source descriptor.
        Output:
            Complete `PolicyEpisode` ready for preview, annotation, or export.
        """
