"""Dexforce W1 teleop raw format package."""

from __future__ import annotations

from univis.core.components import ComponentBundle
from univis.formats.dexforce_w1_teleop.adapter import DexforceW1TeleopAdapter


def dexforce_w1_teleop_components() -> ComponentBundle:
    """Return input adapter components owned by the W1 teleop format."""

    return ComponentBundle(input_adapters=[DexforceW1TeleopAdapter()])


__all__ = ["DexforceW1TeleopAdapter", "dexforce_w1_teleop_components"]
