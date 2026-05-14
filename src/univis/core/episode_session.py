"""Runtime episode source context for the UniVis API."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from univis.adapters.base import EpisodeSource, RawEpisodeAdapter
from univis.adapters.fake_policy_episode import FakePolicyEpisodeAdapter
from univis.adapters.hdf5 import HDF5EpisodeAdapter
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

    def set_source(self, adapter_name: str, root_path: str | None = None) -> dict:
        """Switch the active episode source.

        Inputs:
            adapter_name: Registered adapter component name.
            root_path: Optional file or directory path for file-backed adapters.
        Output:
            JSON-compatible active source summary.
        """

        if adapter_name not in self.adapters:
            raise KeyError(f"unknown adapter: {adapter_name}")
        source = EpisodeSource(root_path=Path(root_path)) if root_path else None
        adapter = self.adapters[adapter_name]
        adapter.list_metadata(source)
        self.active = ActiveSource(adapter_name=adapter_name, source=source)
        return self.source_payload()

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
        items: list[dict] = []
        for metadata in adapter.list_metadata(self.active.source):
            item = metadata.model_dump()
            item["source"] = self.active.adapter_name
            item["conversion"] = self._conversion_state(adapter, metadata)
            items.append(item)
        return items

    def get_metadata(self, episode_id: str) -> PolicyEpisodeMetadata:
        """Return metadata for one active episode."""

        return self.get_episode(episode_id).metadata

    def get_episode(self, episode_id: str) -> PolicyEpisode:
        """Load one active episode."""

        return self._active_adapter().load_episode(episode_id, self.active.source)

    def update_annotation(self, episode_id: str, annotation: Annotation) -> Annotation:
        """Persist annotation for the active source when supported."""

        adapter = self._active_adapter()
        if isinstance(adapter, FakePolicyEpisodeAdapter):
            return adapter.repository.update_annotation(episode_id, annotation)
        if isinstance(adapter, HDF5EpisodeAdapter):
            path = adapter.path_for_episode(episode_id, self.active.source)
            adapter.write_annotation(path, annotation)
            return adapter.load_episode(episode_id, self.active.source).metadata.annotation
        raise NotImplementedError(f"annotation update is not supported by {adapter.info().name}")

    def _active_adapter(self) -> RawEpisodeAdapter:
        """Return the current adapter instance."""

        return self.adapters[self.active.adapter_name]

    def _conversion_state(
        self,
        adapter: RawEpisodeAdapter,
        metadata: PolicyEpisodeMetadata,
    ) -> dict[str, object]:
        """Return UI conversion status for an episode."""

        if isinstance(adapter, FakePolicyEpisodeAdapter):
            return adapter.repository.conversion_state(metadata.episode_id)
        if isinstance(adapter, HDF5EpisodeAdapter):
            return {"status": "converted", "progress": 1.0}
        return {"status": "pending", "progress": 0.0}
