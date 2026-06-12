"""LeRobot v3.0 dataset format package."""

from __future__ import annotations

from univis.core.components import ComponentBundle
from univis.formats.lerobot_v3.adapter import LeRobotV3EpisodeAdapter

FORMAT_ORDER = 20


def format_components() -> ComponentBundle:
    """Return adapter instances owned by this format package."""

    return ComponentBundle(
        input_adapters=[LeRobotV3EpisodeAdapter()],
        output_exporters=[],
    )


__all__ = ["FORMAT_ORDER", "LeRobotV3EpisodeAdapter", "format_components"]
