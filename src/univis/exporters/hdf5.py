"""HDF5 exporter for synchronized PolicyEpisode objects."""

from __future__ import annotations

from pathlib import Path

import h5py
import numpy as np

from univis.core.components import ComponentInfo
from univis.domain.policy_episode import PolicyEpisode
from univis.exporters.base import EpisodeExporter, ExportResult
from univis.utils.hdf5_episode import (
    STRING_DTYPE,
    frames_to_qpos,
    json_dumps,
    write_string_dataset,
)


class HDF5EpisodeExporter(EpisodeExporter):
    """Write a `PolicyEpisode` to the current UniVis-compatible HDF5 schema.

    Inputs:
        None.
    Output:
        Exporter instance that writes one `.hdf5` file per episode.
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
            name="HDF5EpisodeExporter",
            label="Compressed HDF5",
            description="Writes PolicyEpisode data to an HDF5 episode file.",
        )

    def export(self, episode: PolicyEpisode, output_root: Path) -> ExportResult:
        """Export one episode to an HDF5 file.

        Inputs:
            episode: Synchronized episode to write.
            output_root: Directory receiving `<episode_id>.hdf5`.
        Output:
            Export status including written file path.
        """

        output_root.mkdir(parents=True, exist_ok=True)
        output_path = output_root / f"{episode.metadata.episode_id}.hdf5"
        qpos = frames_to_qpos(episode.frames)
        with h5py.File(output_path, "w") as root:
            root.attrs["univis_schema_version"] = "0.1"
            root.attrs["fps"] = float(episode.metadata.fps)
            observations = root.create_group("observations")
            observations.create_dataset("qpos", data=qpos, compression="gzip")
            root.create_dataset("action", data=qpos.copy(), compression="gzip")
            root.create_dataset("chunks", data=np.asarray(1, dtype=np.int32))
            write_string_dataset(
                root,
                "language_prompt",
                episode.metadata.annotation.language_prompt,
            )
            self._write_metadata(root, episode)
        return ExportResult(
            episode_id=episode.metadata.episode_id,
            exporter_name=self.info().name,
            output_path=str(output_path),
            success=True,
            message=f"wrote {episode.metadata.num_frames} frames",
        )

    def _write_metadata(self, root: h5py.File, episode: PolicyEpisode) -> None:
        """Write UniVis-specific metadata groups.

        Inputs:
            root: Open HDF5 file.
            episode: Episode whose metadata should be serialized.
        Output:
            Mutates `root` with camera, annotation, and reachability metadata.
        """

        group = root.create_group("univis")
        group.attrs["title"] = episode.metadata.title
        group.attrs["annotation_json"] = json_dumps(
            episode.metadata.annotation.model_dump()
        )
        cameras = group.create_group("cameras")
        image_group = root["observations"].create_group("images")
        for camera in episode.metadata.cameras:
            cam_group = cameras.create_group(camera.key)
            cam_group.attrs["label"] = camera.label
            cam_group.attrs["width"] = int(camera.width)
            cam_group.attrs["height"] = int(camera.height)
            cam_group.attrs["kind"] = camera.kind
            image_group.create_group(camera.key)
        if episode.metadata.reachability is not None:
            reachability = group.create_group("reachability")
            reachability.create_dataset(
                "reachable",
                data=np.asarray(episode.metadata.reachability.reachable, dtype=np.bool_),
            )
            reachability.create_dataset(
                "reasons",
                data=np.asarray(episode.metadata.reachability.reasons, dtype=object),
                dtype=STRING_DTYPE,
            )
