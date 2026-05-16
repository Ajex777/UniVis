"""HDF5 exporter for synchronized PolicyEpisode objects."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import h5py
import numpy as np
from PIL import Image

from univis.adapters.base import EpisodeSource, RawEpisodeAdapter
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
        image_adapter: Optional adapter used to fetch source camera frames.
        image_source: Optional source descriptor for `image_adapter`.
        image_chunk_size: Number of frames per HDF5 image chunk.
    Output:
        Exporter instance that writes one `.hdf5` file per episode.
    """

    def __init__(
        self,
        image_adapter: RawEpisodeAdapter | None = None,
        image_source: EpisodeSource | None = None,
        image_chunk_size: int = 50,
    ) -> None:
        """Initialize a HDF5 exporter.

        Images stay outside `PolicyEpisode`; when provided, `image_adapter`
        supplies synchronized camera frames lazily during export.
        """

        self.image_adapter = image_adapter
        self.image_source = image_source
        self.image_chunk_size = max(1, int(image_chunk_size))

    def with_image_provider(
        self,
        adapter: RawEpisodeAdapter,
        source: EpisodeSource | None,
    ) -> "HDF5EpisodeExporter":
        """Return an exporter bound to an adapter-backed image provider.

        Inputs:
            adapter: Active source adapter that serves synchronized images.
            source: Active source descriptor for the adapter.
        Output:
            New exporter instance preserving the configured chunk size.
        """

        return HDF5EpisodeExporter(
            image_adapter=adapter,
            image_source=source,
            image_chunk_size=self.image_chunk_size,
        )

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
            self._write_images(root, episode)
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

    def _write_images(self, root: h5py.File, episode: PolicyEpisode) -> None:
        """Write adapter-backed camera frames using the script-compatible layout."""

        if self.image_adapter is None:
            return
        image_group = root["observations"]["images"]
        for camera in episode.metadata.cameras:
            camera_group = image_group[camera.key]
            starts = np.arange(
                0,
                episode.metadata.num_frames,
                self.image_chunk_size,
                dtype=np.int64,
            )
            frame_to_chunk = np.searchsorted(
                starts,
                np.arange(episode.metadata.num_frames, dtype=np.int64),
                side="right",
            ) - 1
            image_group.create_dataset(f"{camera.key}_index", data=frame_to_chunk)
            image_group.create_dataset(f"{camera.key}_start", data=starts)
            for chunk_id, start in enumerate(starts):
                end = min(int(start) + self.image_chunk_size, episode.metadata.num_frames)
                frames = [
                    self._read_bgr_frame(episode, camera.key, frame_index)
                    for frame_index in range(int(start), end)
                ]
                chunk = np.stack(frames, axis=0)
                if chunk.shape[1] != camera.height or chunk.shape[2] != camera.width:
                    raise ValueError(
                        f"camera {camera.key} image shape {chunk.shape[2]}x{chunk.shape[1]} "
                        f"does not match metadata {camera.width}x{camera.height}"
                    )
                flat_chunk = chunk.reshape(chunk.shape[0], chunk.shape[1], chunk.shape[2] * 3)
                camera_group.create_dataset(str(chunk_id), data=flat_chunk, compression="gzip")

    def _read_bgr_frame(
        self,
        episode: PolicyEpisode,
        camera_key: str,
        frame_index: int,
    ) -> np.ndarray:
        """Fetch and decode one adapter image as uint8 BGR."""

        if self.image_adapter is None:
            raise RuntimeError("image adapter is not configured")
        encoded = self.image_adapter.get_image_frame(
            episode.metadata.episode_id,
            camera_key,
            frame_index,
            self.image_source,
        )
        with Image.open(BytesIO(encoded.data)) as image:
            rgb = np.asarray(image.convert("RGB"), dtype=np.uint8)
        return rgb[:, :, ::-1]
