"""LeRobot v3.0 dataset format package."""

from __future__ import annotations

from univis.core.components import ComponentBundle
from univis.formats.lerobot_v3.adapter import LeRobotV3EpisodeAdapter


def lerobot_v3_components() -> ComponentBundle:
    """Return adapter instances owned by this format package."""

    return ComponentBundle(
        input_adapters=[LeRobotV3EpisodeAdapter()],
        output_exporters=[],
    )


__all__ = ["LeRobotV3EpisodeAdapter", "lerobot_v3_components"]
