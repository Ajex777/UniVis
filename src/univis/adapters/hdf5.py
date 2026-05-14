"""HDF5 adapter that loads episode files as PolicyEpisode objects."""

from __future__ import annotations

import json
from pathlib import Path

import h5py
import numpy as np

from univis.adapters.base import EpisodeSource, ImageFrame, RawEpisodeAdapter, SourceValidation
from univis.core.components import ComponentInfo
from univis.domain.policy_episode import (
    Annotation, CameraStream, PolicyEpisode, PolicyEpisodeMetadata, ReachabilityOverlay,
)
from univis.utils.hdf5_episode import decode_scalar, qpos_to_frames, read_string_dataset
from univis.utils.hdf5_images import (
    camera_streams_from_image_group,
    encode_frame_png,
    read_hdf5_image_frame,
)
from univis.utils.sorting import natural_sort_key


class HDF5EpisodeAdapter(RawEpisodeAdapter):
    """Load current compressed HDF5 episodes into `PolicyEpisode`."""

    @classmethod
    def info(cls) -> ComponentInfo:
        """Return adapter metadata for registry and UI display."""
        return ComponentInfo(
            name="HDF5EpisodeAdapter",
            label="HDF5 Episode",
            description="Reads HDF5 episode files into PolicyEpisode objects.",
        )

    def list_metadata(self, source: EpisodeSource | None = None) -> list[PolicyEpisodeMetadata]:
        """List HDF5 metadata from a file or directory source."""
        return [self._read_metadata(path) for path in self._episode_paths(source)]

    def validate_source(self, source: EpisodeSource | None = None) -> SourceValidation:
        """Validate HDF5 file or single-level HDF5 directory input."""
        try:
            paths = self._episode_paths(source)
            if not paths:
                return SourceValidation(
                    valid=False,
                    message="HDF5 source must contain .hdf5 or .h5 files at top level",
                )
            return SourceValidation(
                valid=True,
                message=f"found {len(paths)} HDF5 episode file(s)",
                episode_count=len(paths),
            )
        except Exception as exc:
            return SourceValidation(valid=False, message=str(exc))

    def load_episode(
        self,
        episode_id: str,
        source: EpisodeSource | None = None,
    ) -> PolicyEpisode:
        """Load one synchronized HDF5 episode."""
        path = self.path_for_episode(episode_id, source)
        with h5py.File(path, "r") as root:
            metadata = self._read_metadata(path, root)
            qpos = np.asarray(root["observations"]["qpos"][:], dtype=np.float32)
        return PolicyEpisode(metadata=metadata, frames=qpos_to_frames(qpos, metadata.fps))

    def get_image_frame(
        self,
        episode_id: str,
        camera_key: str,
        frame_index: int,
        source: EpisodeSource | None = None,
    ) -> ImageFrame:
        """Return one PNG frame from HDF5 `observations/images` chunks."""
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
        """Return a contiguous PNG frame batch from one HDF5 open."""
        path = self.path_for_episode(episode_id, source)
        start = max(0, int(start_index))
        frames: list[ImageFrame] = []
        try:
            with h5py.File(path, "r") as root:
                meta = self._read_metadata(path, root)
                end = min(meta.num_frames, start + max(0, int(count)))
                images = root["observations"]["images"]
                for idx in range(start, end):
                    frame = read_hdf5_image_frame(images, camera_key, idx)
                    frames.append(ImageFrame(encode_frame_png(frame), "image/png"))
        except OSError as exc:
            raise RuntimeError(
                "failed to decode HDF5 image frame; h5ffmpeg filter may be missing"
            ) from exc
        return frames

    def path_for_episode(self, episode_id: str, source: EpisodeSource | None) -> Path:
        """Find the HDF5 path matching an episode id."""
        for path in self._episode_paths(source):
            if episode_id in {path.stem, path.name}:
                return path
        raise KeyError(f"episode not found: {episode_id}")

    def write_annotation(self, hdf5_path: Path, annotation: Annotation) -> None:
        """Write back HDF5 language prompt and UniVis annotation metadata."""
        from univis.utils.hdf5_episode import write_string_dataset

        with h5py.File(hdf5_path, "r+") as root:
            write_string_dataset(root, "language_prompt", annotation.language_prompt)
            group = root.require_group("univis")
            group.attrs["annotation_json"] = json.dumps(
                annotation.model_dump(),
                ensure_ascii=False,
                separators=(",", ":"),
            )

    def write_language_prompt(self, hdf5_path: Path, language_prompt: str) -> None:
        """Write back the HDF5 `language_prompt` dataset."""
        from univis.utils.hdf5_episode import write_string_dataset

        with h5py.File(hdf5_path, "r+") as root:
            write_string_dataset(root, "language_prompt", language_prompt)
            if "univis" in root and "annotation_json" in root["univis"].attrs:
                annotation = self._read_annotation(root).model_copy(
                    update={"language_prompt": language_prompt}
                )
                root["univis"].attrs["annotation_json"] = json.dumps(
                    annotation.model_dump(),
                    ensure_ascii=False,
                    separators=(",", ":"),
                )

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
            nested = [
                child
                for child in root.iterdir()
                if child.is_dir()
                and any(p.suffix.lower() in {".hdf5", ".h5"} for p in child.iterdir())
            ]
            if nested:
                raise ValueError("HDF5 source supports only one directory level")
        return sorted(paths, key=lambda path: natural_sort_key(path.name))

    def _read_metadata(
        self,
        path: Path,
        root: h5py.File | None = None,
    ) -> PolicyEpisodeMetadata:
        """Read metadata without decoding image frames."""
        if root is None:
            with h5py.File(path, "r") as opened:
                return self._read_metadata(path, opened)
        qpos = np.asarray(root["observations"]["qpos"])
        num_frames = 1 if qpos.ndim == 1 else int(qpos.shape[0])
        fps = float(decode_scalar(root.attrs.get("fps", 12.0)) or 12.0)
        title = path.stem
        if "univis" in root:
            title = str(decode_scalar(root["univis"].attrs.get("title", path.stem)))
        return PolicyEpisodeMetadata(
            episode_id=path.stem,
            title=title,
            num_frames=num_frames,
            fps=fps,
            cameras=self._read_cameras(root),
            annotation=self._read_annotation(root),
            reachability=self._read_reachability(root, num_frames),
        )

    def _read_cameras(self, root: h5py.File) -> list[CameraStream]:
        """Read camera metadata from UniVis or observations/images groups."""
        if "univis" in root and "cameras" in root["univis"]:
            return [
                self._camera_from_group(key, group)
                for key, group in root["univis"]["cameras"].items()
            ]
        if "observations" not in root or "images" not in root["observations"]:
            return []
        return camera_streams_from_image_group(root["observations"]["images"])

    def _camera_from_group(self, key: str, group: h5py.Group) -> CameraStream:
        """Build one camera stream from an HDF5 metadata group."""
        return CameraStream(
            key=key,
            label=str(decode_scalar(group.attrs.get("label", key))),
            width=int(decode_scalar(group.attrs.get("width", 640))),
            height=int(decode_scalar(group.attrs.get("height", 360))),
            kind=str(decode_scalar(group.attrs.get("kind", "rgb"))),
        )

    def _read_annotation(self, root: h5py.File) -> Annotation:
        """Read HDF5 annotation metadata."""
        prompt = read_string_dataset(root, "language_prompt")
        if "univis" in root and "annotation_json" in root["univis"].attrs:
            raw_payload = decode_scalar(root["univis"].attrs["annotation_json"])
            payload = json.loads(str(raw_payload))
            payload["language_prompt"] = prompt or payload.get("language_prompt", "")
            return Annotation(**payload)
        return Annotation(language_prompt=prompt)

    def _read_reachability(
        self,
        root: h5py.File,
        num_frames: int,
    ) -> ReachabilityOverlay | None:
        """Read optional reachability overlay metadata."""
        if "univis" not in root or "reachability" not in root["univis"]:
            return None
        group = root["univis"]["reachability"]
        reachable = [bool(value) for value in group["reachable"][:]]
        reasons = [str(decode_scalar(value)) for value in group["reasons"][:]]
        if len(reachable) != num_frames or len(reasons) != num_frames:
            return None
        return ReachabilityOverlay(reachable=reachable, reasons=reasons)
