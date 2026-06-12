"""Exporter for dexechain-compatible compressed HDF5 policy episodes."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import h5py
import numpy as np
from PIL import Image

from univis.base_io.adapters import EpisodeSource, RawEpisodeAdapter
from univis.core.components import ComponentInfo
from univis.domain.policy_episode import PolicyEpisode
from univis.base_io.exporters import EpisodeExporter, ExportResult
from univis.formats.compressed_hdf5.codec import DexH5FFmpegCodec, HDF5VideoCodec
from univis.formats.compressed_hdf5.schema import ACTION, CHUNKS, IMAGES, LANGUAGE_PROMPT, OBSERVATIONS, QPOS, CompressedHDF5Schema
from univis.utils.hdf5_episode import STRING_DTYPE, frames_to_qpos, json_dumps, write_string_dataset


class HDF5EpisodeExporter(EpisodeExporter):
    """Write `PolicyEpisode` data using dexechain compressed HDF5 layout."""

    def __init__(
        self,
        image_adapter: RawEpisodeAdapter | None = None,
        image_source: EpisodeSource | None = None,
        image_chunk_size: int = 50,
        video_codec: HDF5VideoCodec | None = None,
    ) -> None:
        """Initialize adapter-backed image export settings."""

        self.image_adapter = image_adapter
        self.image_source = image_source
        self.image_chunk_size = max(1, int(image_chunk_size))
        self.video_codec = video_codec or DexH5FFmpegCodec.from_environment()

    def with_image_provider(
        self,
        adapter: RawEpisodeAdapter,
        source: EpisodeSource | None,
    ) -> "HDF5EpisodeExporter":
        """Return an exporter bound to an adapter-backed image provider."""

        return HDF5EpisodeExporter(adapter, source, self.image_chunk_size, self.video_codec)

    @classmethod
    def info(cls) -> ComponentInfo:
        """Return exporter metadata for registry and UI display."""

        return ComponentInfo(
            name="HDF5EpisodeExporter",
            label="Compressed HDF5",
            aliases=["HDF5"],
            description="Writes dexechain-compatible compressed HDF5 episode files.",
            capabilities={"format": {"schema": "dexechain_compressed_hdf5"}},
        )

    def export(self, episode: PolicyEpisode, output_root: Path) -> ExportResult:
        """Export one episode to `<episode_id>.hdf5`."""

        if episode.metadata.cameras and self.image_adapter is None:
            raise RuntimeError("compressed HDF5 export requires an adapter-backed image provider")
        output_root.mkdir(parents=True, exist_ok=True)
        output_path = output_root / f"{episode.metadata.episode_id}.hdf5"
        qpos = frames_to_qpos(episode.frames)
        chunk_count = self._chunk_count(episode)
        with h5py.File(output_path, "w") as root:
            root.attrs["univis_schema_version"] = "0.1"
            root.attrs["fps"] = float(episode.metadata.fps)
            observations = root.create_group(OBSERVATIONS)
            observations.create_dataset(QPOS, data=qpos)
            root.create_dataset(ACTION, data=qpos.copy())
            root.create_dataset(CHUNKS, data=np.asarray(chunk_count))
            write_string_dataset(root, LANGUAGE_PROMPT, episode.metadata.annotation.language_prompt)
            self._write_metadata(root, episode)
            self._write_images(root, episode, chunk_count)
        return ExportResult(
            episode_id=episode.metadata.episode_id,
            exporter_name=self.info().name,
            output_path=str(output_path),
            success=True,
            message=f"wrote {episode.metadata.num_frames} frames in {chunk_count} chunk(s)",
        )

    def _chunk_count(self, episode: PolicyEpisode) -> int:
        """Compute dexechain-style total chunk count from frames-per-chunk."""

        return max(1, int(np.ceil(episode.metadata.num_frames / self.image_chunk_size)))

    def _write_metadata(self, root: h5py.File, episode: PolicyEpisode) -> None:
        """Write UniVis metadata without affecting dexechain root schema."""

        group = root.create_group("univis")
        group.attrs["title"] = episode.metadata.title
        group.attrs["annotation_json"] = json_dumps(episode.metadata.annotation.model_dump())
        cameras = group.create_group("cameras")
        for camera in episode.metadata.cameras:
            cam_group = cameras.create_group(camera.key)
            cam_group.attrs["label"] = camera.label
            cam_group.attrs["width"] = int(camera.width)
            cam_group.attrs["height"] = int(camera.height)
            cam_group.attrs["kind"] = camera.kind
        if episode.metadata.reachability is not None:
            reachability = group.create_group("reachability")
            reachability.create_dataset("reachable", data=np.asarray(episode.metadata.reachability.reachable, dtype=np.bool_))
            reachability.create_dataset("reasons", data=np.asarray(episode.metadata.reachability.reasons, dtype=object), dtype=STRING_DTYPE)

    def _write_images(self, root: h5py.File, episode: PolicyEpisode, chunk_count: int) -> None:
        """Write adapter-backed camera frames using dexechain chunk side tables."""

        image_group = root[OBSERVATIONS].create_group(IMAGES)
        chunk_indices = CompressedHDF5Schema.split_indices(episode.metadata.num_frames, chunk_count)
        for camera in episode.metadata.cameras:
            camera_group = image_group.create_group(camera.key)
            frame_to_chunk = np.zeros((episode.metadata.num_frames,))
            starts = np.zeros((chunk_count,))
            for chunk_id, indices in enumerate(chunk_indices):
                starts[chunk_id] = int(indices[0]) if len(indices) else 0
                frame_to_chunk[indices] = float(chunk_id)
            image_group.create_dataset(CompressedHDF5Schema.chunk_name(camera.key, "index"), data=frame_to_chunk)
            image_group.create_dataset(CompressedHDF5Schema.chunk_name(camera.key, "start"), data=starts)
            for chunk_id, indices in enumerate(chunk_indices):
                chunk = self._read_chunk(episode, camera.key, indices)
                flat_chunk = CompressedHDF5Schema.to_bhw(chunk)
                camera_group.create_dataset(
                    str(chunk_id),
                    data=flat_chunk,
                    chunks=flat_chunk.shape,
                    **self.video_codec.dataset_kwargs(IMAGES),
                )

    def _read_chunk(self, episode: PolicyEpisode, camera_key: str, indices: np.ndarray) -> np.ndarray:
        """Fetch and decode one camera chunk as uint8 BGR frames."""

        frames = [self._read_bgr_frame(episode, camera_key, int(index)) for index in indices]
        if not frames:
            raise ValueError(f"empty chunk for camera {camera_key}")
        return np.stack(frames, axis=0)

    def _read_bgr_frame(self, episode: PolicyEpisode, camera_key: str, frame_index: int) -> np.ndarray:
        """Fetch one adapter image and convert it to dexechain BGR order."""

        if self.image_adapter is None:
            raise RuntimeError("image adapter is not configured")
        encoded = self.image_adapter.get_image_frame(episode.metadata.episode_id, camera_key, frame_index, self.image_source)
        with Image.open(BytesIO(encoded.data)) as image:
            rgb = np.asarray(image.convert("RGB"), dtype=np.uint8)
        return rgb[:, :, ::-1]
