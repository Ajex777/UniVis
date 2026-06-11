"""Runtime episode source context for the UniVis API."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from univis.adapters.base import (
    EpisodeSource,
    ImageFrame,
    RawEpisodeAdapter,
)
from univis.domain.policy_episode import Annotation, PolicyEpisode, PolicyEpisodeMetadata


@dataclass
class ActiveSource:
    """Current adapter/source selection.

    Inputs:
        adapter_name: Registered adapter component name.
        source: Optional adapter-specific source descriptor.
    Output:
        Small state object used by `EpisodeSession`.
    """

    adapter_name: str
    source: EpisodeSource | None = None


class EpisodeSession:
    """Owns the currently selected episode source.

    Inputs:
        adapters: Adapter instances keyed by `info().name`.
        default_adapter_name: Adapter selected on startup.
    Output:
        Session object used by API routes for list/load/update operations.
    """

    def __init__(
        self,
        adapters: list[RawEpisodeAdapter],
        default_adapter_name: str,
    ) -> None:
        """Initialize the session.

        Inputs:
            adapters: Registered adapter instances.
            default_adapter_name: Initial adapter name.
        Output:
            Session with active source pointing at the default adapter.
        """

        self.adapters = {adapter.info().name: adapter for adapter in adapters}
        if default_adapter_name not in self.adapters:
            raise KeyError(f"unknown default adapter: {default_adapter_name}")
        self.active = ActiveSource(adapter_name=default_adapter_name)
        self._episode_cache: dict[str, PolicyEpisode] = {}
        self._metadata_cache: dict[str, PolicyEpisodeMetadata] = {}

    def set_source(
        self,
        adapter_name: str,
        root_path: str | None = None,
        validate: bool = True,
    ) -> dict:
        """Switch the active episode source.

        Inputs:
            adapter_name: Registered adapter component name.
            root_path: Optional file or directory path for file-backed adapters.
            validate: Whether to run adapter validation before switching.
        Output:
            JSON-compatible active source summary.
        """

        if adapter_name not in self.adapters:
            raise KeyError(f"unknown adapter: {adapter_name}")
        source = EpisodeSource(root_path=Path(root_path)) if root_path else None
        adapter = self.adapters[adapter_name]
        if validate:
            validation = adapter.validate_source(source)
            if not validation.valid:
                raise ValueError(validation.message)
        self.active = ActiveSource(adapter_name=adapter_name, source=source)
        self._episode_cache.clear()
        self._metadata_cache.clear()
        adapter.clear_caches()
        return self.source_payload()

    def validate_source(self, adapter_name: str, root_path: str | None = None) -> dict:
        """Validate an adapter/source pair without changing active source."""

        if adapter_name not in self.adapters:
            raise KeyError(f"unknown adapter: {adapter_name}")
        source = EpisodeSource(root_path=Path(root_path)) if root_path else None
        return self.adapters[adapter_name].validate_source(source).model_dump()

    def source_payload(self) -> dict:
        """Return active source metadata.

        Inputs:
            None.
        Output:
            JSON-compatible source state.
        """

        root_path = self.active.source.root_path if self.active.source else None
        return {
            "input_adapter": self.active.adapter_name,
            "root_path": str(root_path) if root_path else "",
        }

    def list_episodes(self) -> list[dict]:
        """List active source episodes.

        Inputs:
            None.
        Output:
            JSON-compatible metadata list with source/conversion hints.
        """

        adapter = self._active_adapter()
        validation = adapter.validate_source(self.active.source)
        if not validation.valid:
            return []
        items: list[dict] = []
        for metadata in adapter.list_metadata(self.active.source):
            item = metadata.model_dump()
            item["source"] = self.active.adapter_name
            item["conversion"] = self._conversion_state(adapter, metadata)
            items.append(item)
        return items

    def get_metadata(self, episode_id: str) -> PolicyEpisodeMetadata:
        """Return metadata for one active episode (cached)."""

        if episode_id in self._metadata_cache:
            return self._metadata_cache[episode_id]
        episode = self.get_episode(episode_id)
        self._metadata_cache[episode_id] = episode.metadata
        return episode.metadata

    def get_episode(self, episode_id: str) -> PolicyEpisode:
        """Load one active episode (cached)."""

        if episode_id in self._episode_cache:
            return self._episode_cache[episode_id]
        episode = self._active_adapter().load_episode(episode_id, self.active.source)
        self._episode_cache[episode_id] = episode
        self._metadata_cache[episode_id] = episode.metadata
        return episode

    def get_image_frame(
        self,
        episode_id: str,
        camera_key: str,
        frame_index: int,
    ) -> ImageFrame:
        """Read one encoded frame from the active adapter."""

        return self._active_adapter().get_image_frame(
            episode_id,
            camera_key,
            frame_index,
            self.active.source,
        )

    def get_image_frames(
        self,
        episode_id: str,
        camera_key: str,
        start_index: int,
        count: int,
    ) -> list[ImageFrame]:
        """Read a contiguous encoded frame batch from the active adapter."""

        return self._active_adapter().get_image_frames(
            episode_id,
            camera_key,
            start_index,
            count,
            self.active.source,
        )

    def update_annotation(self, episode_id: str, annotation: Annotation) -> Annotation:
        """Persist annotation for the active source when supported."""

        adapter = self._active_adapter()
        result = adapter.update_annotation(episode_id, annotation, self.active.source)
        self._episode_cache.pop(episode_id, None)
        self._metadata_cache.pop(episode_id, None)
        return result

    def _active_adapter(self) -> RawEpisodeAdapter:
        """Return the current adapter instance."""

        return self.adapters[self.active.adapter_name]

    def _conversion_state(
        self,
        adapter: RawEpisodeAdapter,
        metadata: PolicyEpisodeMetadata,
    ) -> dict[str, object]:
        """Return UI conversion status for an episode."""

        conversion = adapter.info().capabilities.get("conversion", {})
        if isinstance(conversion, dict) and "default_status" in conversion:
            return {
                "status": conversion.get("default_status", "pending"),
                "progress": conversion.get("default_progress", 0.0),
            }
        return {"status": "pending", "progress": 0.0}
