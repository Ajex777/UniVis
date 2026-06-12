"""Base classes for exporting PolicyEpisode objects."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from pydantic import BaseModel

from univis.core.components import ComponentInfo
from univis.domain.policy_episode import PolicyEpisode


class ExportResult(BaseModel):
    """Result returned by an episode exporter.

    Inputs:
        episode_id: Exported episode id.
        exporter_name: Component name that produced this result.
        output_path: Destination path or logical target.
        success: Whether export completed successfully.
        message: Optional human-readable status.
    Output:
        Serializable export status for jobs and tests.
    """

    episode_id: str
    exporter_name: str
    output_path: str
    success: bool
    message: str = ""


class EpisodeExporter(ABC):
    """Abstract exporter for pluggable output formats.

    Inputs:
        Concrete implementations receive a synchronized `PolicyEpisode`.
    Output:
        A format-specific artifact and a serializable `ExportResult`.
    """

    @classmethod
    @abstractmethod
    def info(cls) -> ComponentInfo:
        """Return exporter metadata.

        Inputs:
            None.
        Output:
            Component metadata used by registries and UI dropdowns.
        """

    @abstractmethod
    def export(self, episode: PolicyEpisode, output_root: Path) -> ExportResult:
        """Export one episode.

        Inputs:
            episode: Synchronized episode to export.
            output_root: Directory or logical root for output artifacts.
        Output:
            Export status including target path.
        """
