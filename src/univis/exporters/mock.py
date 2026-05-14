"""Mock exporter used to validate the Phase 01 export interface."""

from __future__ import annotations

from pathlib import Path

from univis.core.components import ComponentInfo
from univis.domain.policy_episode import PolicyEpisode
from univis.exporters.base import EpisodeExporter, ExportResult


class MockEpisodeExporter(EpisodeExporter):
    """Exporter that validates flow without writing data files.

    Inputs:
        None.
    Output:
        Exporter instance returning deterministic logical output paths.
    """

    @classmethod
    def info(cls) -> ComponentInfo:
        """Return exporter metadata.

        Inputs:
            None.
        Output:
            Component metadata for registry and UI display.
        """

        return ComponentInfo(
            name="MockEpisodeExporter",
            label="Mock Exporter",
            description="No-op exporter for Phase 01 flow validation.",
        )

    def export(self, episode: PolicyEpisode, output_root: Path) -> ExportResult:
        """Return a successful mock export result.

        Inputs:
            episode: Synchronized episode to validate.
            output_root: Logical output directory.
        Output:
            Success result containing the would-be JSON artifact path.
        """

        output_path = output_root / f"{episode.metadata.episode_id}.mock.json"
        return ExportResult(
            episode_id=episode.metadata.episode_id,
            exporter_name=self.info().name,
            output_path=str(output_path),
            success=True,
            message=f"validated {episode.metadata.num_frames} frames",
        )
