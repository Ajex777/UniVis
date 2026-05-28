"""PIKA raw format package."""

from __future__ import annotations

from univis.core.components import ComponentBundle
from univis.formats.pika_raw.adapter import PikaRawEpisodeAdapter


def pika_raw_components() -> ComponentBundle:
    """Return input adapter components owned by the PIKA raw format."""

    return ComponentBundle(input_adapters=[PikaRawEpisodeAdapter()])


__all__ = ["PikaRawEpisodeAdapter", "pika_raw_components"]
