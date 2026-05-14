"""HDF5 adapter that loads episode files as PolicyEpisode objects."""

from __future__ import annotations

import json
from pathlib import Path

import h5py
import numpy as np

from univis.adapters.base import EpisodeSource, RawEpisodeAdapter
from univis.core.components import ComponentInfo
from univis.domain.policy_episode import (
    Annotation,
    CameraStream,
    PolicyEpisode,
    PolicyEpisodeMetadata,
    ReachabilityOverlay,
)
from univis.utils.hdf5_episode import decode_scalar, qpos_to_frames, read_string_dataset
from univis.utils.sorting import natural_sort_key


class HDF5EpisodeAdapter(RawEpisodeAdapter):
    """Load UniVis/current compressed HDF5 episodes into `PolicyEpisode`.

    Inputs:
        None.
    Output:
        Adapter instance for listing and loading `.hdf5`/`.h5` episode files.
    """

    @classmethod
    def info(cls) -> ComponentInfo:
        """Return adapter metadata.

        Inputs:
            None.
        Output:
            Component metadata for registry and UI display.
        """

        return ComponentInfo(
            name="HDF5EpisodeAdapter",
            label="HDF5 Episode",
            description="Reads HDF5 episode files into PolicyEpisode objects.",
        )

    def list_metadata(self, source: EpisodeSource | None = None) -> list[PolicyEpisodeMetadata]:
        """List HDF5 episode metadata from a file or directory source.

        Inputs:
            source: Source whose `root_path` is a `.hdf5`/`.h5` file or directory.
        Output:
            Metadata for every readable HDF5 file in natural sort order.
        """

        return [self._read_metadata(path) for path in self._episode_paths(source)]

    def load_episode(
        self,
        episode_id: str,
        source: EpisodeSource | None = None,
    ) -> PolicyEpisode:
        """Load one HDF5 episode.

        Inputs:
            episode_id: File stem returned by `list_metadata`.
            source: HDF5 file or directory source.
        Output:
            Complete `PolicyEpisode` with synchronized dual-arm frames.
        """

        path = self.path_for_episode(episode_id, source)
        with h5py.File(path, "r") as root:
            metadata = self._read_metadata(path, root)
            qpos = np.asarray(root["observations"]["qpos"][:], dtype=np.float32)
        return PolicyEpisode(metadata=metadata, frames=qpos_to_frames(qpos, metadata.fps))

    def path_for_episode(self, episode_id: str, source: EpisodeSource | None) -> Path:
        """Find the HDF5 path matching an episode id.

        Inputs:
            episode_id: File stem or filename.
            source: Source descriptor.
        Output:
            Matching HDF5 file path.
        """

        for path in self._episode_paths(source):
            if episode_id in {path.stem, path.name}:
                return path
        raise KeyError(f"episode not found: {episode_id}")

    def write_annotation(self, hdf5_path: Path, annotation: Annotation) -> None:
        """Write back HDF5 language prompt and UniVis annotation metadata.

        Inputs:
            hdf5_path: HDF5 file to update in-place.
            annotation: Full annotation payload from the UI.
        Output:
            Mutates the HDF5 file so future reads see the saved annotation.
        """

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
        """Write back the HDF5 `language_prompt` dataset.

        Inputs:
            hdf5_path: HDF5 file to update in-place.
            language_prompt: New prompt text.
        Output:
            Mutates the HDF5 file so future reads see the new prompt.
        """

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
        """Resolve source paths.

        Inputs:
            source: Optional source descriptor with root path.
        Output:
            HDF5 file paths sorted naturally.
        """

        if source is None or source.root_path is None:
            raise ValueError("HDF5EpisodeAdapter requires source.root_path")
        root = source.root_path.expanduser().resolve()
        if root.is_file() and root.suffix.lower() in {".hdf5", ".h5"}:
            return [root]
        if not root.is_dir():
            raise FileNotFoundError(f"HDF5 source not found: {root}")
        paths = [p for p in root.iterdir() if p.suffix.lower() in {".hdf5", ".h5"}]
        return sorted(paths, key=lambda path: natural_sort_key(path.name))

    def _read_metadata(
        self,
        path: Path,
        root: h5py.File | None = None,
    ) -> PolicyEpisodeMetadata:
        """Read metadata without decoding image frames.

        Inputs:
            path: HDF5 file path.
            root: Optional already-open HDF5 file.
        Output:
            PolicyEpisode metadata.
        """

        if root is None:
            with h5py.File(path, "r") as opened:
                return self._read_metadata(path, opened)
        qpos = np.asarray(root["observations"]["qpos"])
        if qpos.ndim == 1:
            num_frames = 1
        else:
            num_frames = int(qpos.shape[0])
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
        return [
            CameraStream(key=key, label=key, width=640, height=360, kind="rgb")
            for key in root["observations"]["images"].keys()
            if not key.endswith(("_index", "_start"))
        ]

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
