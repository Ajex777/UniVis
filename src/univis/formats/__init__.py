"""Format subpackages exposed to the UniVis application."""

from __future__ import annotations

from univis.core.components import ComponentBundle
from univis.formats.compressed_hdf5 import compressed_hdf5_components
from univis.formats.lerobot_v3 import lerobot_v3_components
from univis.formats.pika_raw import pika_raw_components


def load_format_components() -> ComponentBundle:
    """Instantiate all built-in format package components."""

    components = ComponentBundle()
    for builder in (compressed_hdf5_components, lerobot_v3_components, pika_raw_components):
        bundle = builder()
        components.input_adapters.extend(bundle.input_adapters)
        components.output_exporters.extend(bundle.output_exporters)
    return components
