"""Base classes for converting external data into PolicyEpisode objects."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, Field

from univis.core.components import ComponentInfo
from univis.domain.policy_episode import Annotation, PolicyEpisode, PolicyEpisodeMetadata


class EpisodeSource(BaseModel):
    """Describes an adapter-readable episode source.

    Inputs:
        root_path: Optional local dataset root path.
        options: Adapter-specific options that should remain UI/API agnostic.
    Output:
        Immutable-ish source request passed from orchestration to adapters.
    """

    root_path: Path | None = None
    options: dict[str, str | int | float | bool] = Field(default_factory=dict)


class SourceValidation(BaseModel):
    """Adapter-specific validation result for one source."""

    valid: bool
    message: str
    episode_count: int = 0


@dataclass(frozen=True)
class ImageFrame:
    """Encoded image frame returned by adapters for preview APIs."""

    data: bytes
    media_type: str


class RawEpisodeAdapter(ABC):
    """Abstract adapter that exposes external episodes as PolicyEpisode.

    Inputs:
        Concrete implementations can wrap raw UMI folders, HDF5 files, or
        future EEF-pose datasets.
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

    def validate_source(self, source: EpisodeSource | None = None) -> SourceValidation:
        """Validate whether a source is compatible with this adapter."""

        try:
            metadata = self.list_metadata(source)
        except Exception as exc:
            return SourceValidation(valid=False, message=str(exc), episode_count=0)
        return SourceValidation(
            valid=bool(metadata),
            message=f"found {len(metadata)} episode(s)" if metadata else "no episodes found",
            episode_count=len(metadata),
        )

    def get_image_frame(
        self,
        episode_id: str,
        camera_key: str,
        frame_index: int,
        source: EpisodeSource | None = None,
    ) -> ImageFrame:
        """Return one encoded camera frame when the adapter supports images."""

        raise NotImplementedError(f"image frames are not supported by {self.info().name}")

    def get_image_frames(
        self,
        episode_id: str,
        camera_key: str,
        start_index: int,
        count: int,
        source: EpisodeSource | None = None,
    ) -> list[ImageFrame]:
        """Return a contiguous batch of encoded camera frames."""

        start = max(0, int(start_index))
        total = max(0, int(count))
        return [
            self.get_image_frame(episode_id, camera_key, start + offset, source)
            for offset in range(total)
        ]

    def update_annotation(
        self,
        episode_id: str,
        annotation: Annotation,
        source: EpisodeSource | None = None,
    ) -> Annotation:
        """Persist an episode annotation when the adapter supports writeback.

        Inputs:
            episode_id: Stable episode identifier.
            annotation: Updated annotation payload.
            source: Optional adapter source descriptor.
        Output:
            Saved annotation payload.
        """

        raise NotImplementedError(f"annotation update is not supported by {self.info().name}")
