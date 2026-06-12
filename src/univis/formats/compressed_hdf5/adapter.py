"""Adapter for dexechain-compatible compressed HDF5 policy episodes."""

from __future__ import annotations

import json
from pathlib import Path

import h5py
import numpy as np

from univis.base_io.adapters import EpisodeSource, ImageFrame, RawEpisodeAdapter, SourceValidation
from univis.core.components import ComponentInfo
from univis.domain.policy_episode import Annotation, PolicyEpisode, PolicyEpisodeMetadata, ReachabilityOverlay
from univis.formats.compressed_hdf5.schema import (
    ACTION,
    IMAGES,
    LANGUAGE_PROMPT,
    OBSERVATIONS,
    QPOS,
    CompressedHDF5Schema,
)
from univis.utils.hdf5_episode import decode_scalar, qpos_to_frames, read_string_dataset, write_string_dataset
from univis.utils.sorting import natural_sort_key

try:
    import h5ffmpeg  # noqa: F401
except Exception:
    pass

class HDF5EpisodeAdapter(RawEpisodeAdapter):
    """Load dexechain compressed HDF5 episodes into `PolicyEpisode`."""

    def __init__(self) -> None:
        """Initialize adapter with an in-memory chunk cache."""

        self._chunk_cache: dict[tuple[str, str, int], np.ndarray] = {}

    def clear_caches(self) -> None:
        """Drop chunk cache when switching source."""

        self._chunk_cache.clear()

    @classmethod
    def info(cls) -> ComponentInfo:
        """Return adapter metadata for registry and UI display."""

        return ComponentInfo(
            name="HDF5EpisodeAdapter",
            label="Compressed HDF5",
            aliases=["HDF5"],
            description="Reads dexechain-compatible compressed HDF5 episode files.",
            capabilities={
                "source": {
                    "directory_upload": "top_level_matching",
                    "file_extensions": [".hdf5", ".h5"],
                    "supports_file_upload": True,
                },
                "conversion": {"default_status": "converted", "default_progress": 1.0},
            },
        )

    def list_metadata(self, source: EpisodeSource | None = None) -> list[PolicyEpisodeMetadata]:
        """List strict compressed HDF5 metadata from a file or directory source."""

        return [self._read_metadata(path) for path in self._episode_paths(source)]

    def validate_source(self, source: EpisodeSource | None = None) -> SourceValidation:
        """Validate HDF5 file or single-level compressed HDF5 directory input."""

        try:
            paths = self._episode_paths(source)
            if not paths:
                return SourceValidation(
                    valid=False,
                    message="HDF5 source must contain .hdf5 or .h5 files at top level",
                )
            for path in paths:
                with h5py.File(path, "r") as root:
                    CompressedHDF5Schema.require_file(root)
            return SourceValidation(
                valid=True,
                message=f"found {len(paths)} compressed HDF5 episode file(s)",
                episode_count=len(paths),
            )
        except Exception as exc:
            return SourceValidation(valid=False, message=str(exc))

    def load_episode(self, episode_id: str, source: EpisodeSource | None = None) -> PolicyEpisode:
        """Load one synchronized compressed HDF5 policy episode."""

        path = self.path_for_episode(episode_id, source)
        with h5py.File(path, "r") as root:
            CompressedHDF5Schema.require_file(root)
            metadata = self._read_metadata(path, root)
            qpos = np.asarray(root[OBSERVATIONS][QPOS][:], dtype=np.float32)
        return PolicyEpisode(metadata=metadata, frames=qpos_to_frames(qpos, metadata.fps))

    def get_image_frame(
        self,
        episode_id: str,
        camera_key: str,
        frame_index: int,
        source: EpisodeSource | None = None,
    ) -> ImageFrame:
        """Return one preview frame decoded from compressed HDF5 chunks."""

        frames = self.get_image_frames(episode_id, camera_key, frame_index, 1, source)
        if not frames:
            raise IndexError("frame batch is empty")
        return frames[0]

    def get_image_frames(
        self,
        episode_id: str,
        camera_key: str,
        start_index: int,
        count: int,
        source: EpisodeSource | None = None,
    ) -> list[ImageFrame]:
        """Return JPEG preview frames with in-memory chunk caching.

        Decoded BHWC chunks are cached so sequential playback through the
        same chunk avoids repeated h5ffmpeg decompression. Preview frames
        use JPEG for fast PIL encode and small payload.
        """

        path = self.path_for_episode(episode_id, source)
        frames: list[ImageFrame] = []
        with h5py.File(path, "r") as root:
            meta = self._read_metadata(path, root)
            images = root[OBSERVATIONS][IMAGES]
            start = max(0, int(start_index))
            end = min(meta.num_frames, start + max(0, int(count)))
            for idx in range(start, end):
                chunk_id = CompressedHDF5Schema._chunk_id(images, camera_key, idx)
                cache_key = (episode_id, camera_key, chunk_id)
                if cache_key in self._chunk_cache:
                    chunk = self._chunk_cache[cache_key]
                else:
                    chunk = CompressedHDF5Schema.to_bhwc(
                        np.asarray(images[camera_key][str(chunk_id)][:])
                    )
                    self._chunk_cache[cache_key] = chunk
                    if len(self._chunk_cache) > 12:
                        self._chunk_cache.pop(next(iter(self._chunk_cache)))
                local = int(idx) - CompressedHDF5Schema._chunk_start(images, camera_key, chunk_id)
                frame_data = chunk[max(0, min(local, chunk.shape[0] - 1))]
                data, media_type = CompressedHDF5Schema.encode_frame_preview(frame_data)
                frames.append(ImageFrame(data=data, media_type=media_type))
        return frames

    def path_for_episode(self, episode_id: str, source: EpisodeSource | None) -> Path:
        """Find the HDF5 path matching an episode id."""

        for path in self._episode_paths(source):
            if episode_id in {path.stem, path.name}:
                return path
        raise KeyError(f"episode not found: {episode_id}")

    def update_annotation(
        self,
        episode_id: str,
        annotation: Annotation,
        source: EpisodeSource | None = None,
    ) -> Annotation:
        """Persist annotation updates for one compressed HDF5 episode."""

        path = self.path_for_episode(episode_id, source)
        self.write_annotation(path, annotation)
        return self.load_episode(episode_id, source).metadata.annotation

    def write_annotation(self, hdf5_path: Path, annotation: Annotation) -> None:
        """Write back language prompt and UniVis annotation metadata."""

        with h5py.File(hdf5_path, "r+") as root:
            write_string_dataset(root, LANGUAGE_PROMPT, annotation.language_prompt)
            group = root.require_group("univis")
            group.attrs["annotation_json"] = json.dumps(annotation.model_dump(), ensure_ascii=False, separators=(",", ":"))

    def write_language_prompt(self, hdf5_path: Path, language_prompt: str) -> None:
        """Write back the root `language_prompt` dataset."""

        with h5py.File(hdf5_path, "r+") as root:
            write_string_dataset(root, LANGUAGE_PROMPT, language_prompt)
            if "univis" in root and "annotation_json" in root["univis"].attrs:
                annotation = self._read_annotation(root).model_copy(update={"language_prompt": language_prompt})
                root["univis"].attrs["annotation_json"] = json.dumps(annotation.model_dump(), ensure_ascii=False, separators=(",", ":"))

    def _episode_paths(self, source: EpisodeSource | None) -> list[Path]:
        """Resolve source paths into naturally sorted HDF5 files."""

        if source is None or source.root_path is None:
            raise ValueError("HDF5EpisodeAdapter requires source.root_path")
        root = source.root_path.expanduser().resolve()
        if root.is_file() and root.suffix.lower() in {".hdf5", ".h5"}:
            return [root]
        if not root.is_dir():
            raise FileNotFoundError(f"HDF5 source not found: {root}")
        paths = [p for p in root.iterdir() if p.suffix.lower() in {".hdf5", ".h5"}]
        if not paths:
            nested = [child for child in root.iterdir() if child.is_dir() and any(p.suffix.lower() in {".hdf5", ".h5"} for p in child.iterdir())]
            if nested:
                raise ValueError("HDF5 source supports only one directory level")
        return sorted(paths, key=lambda path: natural_sort_key(path.name))

    def _read_metadata(self, path: Path, root: h5py.File | None = None) -> PolicyEpisodeMetadata:
        """Read metadata without decoding image payloads."""

        if root is None:
            with h5py.File(path, "r") as opened:
                return self._read_metadata(path, opened)
        CompressedHDF5Schema.require_file(root)
        qpos = np.asarray(root[OBSERVATIONS][QPOS])
        num_frames = 1 if qpos.ndim == 1 else int(qpos.shape[0])
        fps = float(decode_scalar(root.attrs.get("fps", 12.0)) or 12.0)
        title = str(decode_scalar(root["univis"].attrs.get("title", path.stem))) if "univis" in root else path.stem
        return PolicyEpisodeMetadata(
            episode_id=path.stem,
            title=title,
            num_frames=num_frames,
            fps=fps,
            cameras=CompressedHDF5Schema.camera_streams(root[OBSERVATIONS][IMAGES]),
            annotation=self._read_annotation(root),
            reachability=self._read_reachability(root, num_frames),
        )

    def _read_annotation(self, root: h5py.File) -> Annotation:
        """Read HDF5 annotation metadata."""

        prompt = read_string_dataset(root, LANGUAGE_PROMPT)
        if "univis" in root and "annotation_json" in root["univis"].attrs:
            payload = json.loads(str(decode_scalar(root["univis"].attrs["annotation_json"])))
            payload["language_prompt"] = prompt or payload.get("language_prompt", "")
            return Annotation(**payload)
        return Annotation(language_prompt=prompt)

    def _read_reachability(self, root: h5py.File, num_frames: int) -> ReachabilityOverlay | None:
        """Read optional UniVis reachability overlay metadata."""

        if "univis" not in root or "reachability" not in root["univis"]:
            return None
        group = root["univis"]["reachability"]
        reachable = [bool(value) for value in group["reachable"][:]]
        reasons = [str(decode_scalar(value)) for value in group["reasons"][:]]
        if len(reachable) != num_frames or len(reasons) != num_frames:
            return None
        return ReachabilityOverlay(reachable=reachable, reasons=reasons)
