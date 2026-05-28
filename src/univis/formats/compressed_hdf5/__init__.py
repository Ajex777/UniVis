"""Dexechain-compatible compressed HDF5 format package."""

from __future__ import annotations

from univis.core.components import ComponentBundle
from univis.formats.compressed_hdf5.adapter import HDF5EpisodeAdapter
from univis.formats.compressed_hdf5.exporter import HDF5EpisodeExporter


def compressed_hdf5_components() -> ComponentBundle:
    """Return adapter/exporter instances owned by this format package."""

    return ComponentBundle(
        input_adapters=[HDF5EpisodeAdapter()],
        output_exporters=[HDF5EpisodeExporter()],
    )


__all__ = ["HDF5EpisodeAdapter", "HDF5EpisodeExporter", "compressed_hdf5_components"]
