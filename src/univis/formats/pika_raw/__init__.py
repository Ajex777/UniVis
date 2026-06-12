"""PIKA raw format package."""

from __future__ import annotations

from univis.core.components import ComponentBundle
from univis.formats.pika_raw.adapter import PikaRawEpisodeAdapter

FORMAT_ORDER = 30


def format_components() -> ComponentBundle:
    """Return input adapter components owned by the PIKA raw format."""

    return ComponentBundle(input_adapters=[PikaRawEpisodeAdapter()])


__all__ = ["FORMAT_ORDER", "PikaRawEpisodeAdapter", "format_components"]
