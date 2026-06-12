"""Image masking preprocessor — black out camera frames for one side."""

from __future__ import annotations

from io import BytesIO

from PIL import Image

from univis.base_io.adapters import ImageFrame, RawEpisodeAdapter
from univis.core.components import ComponentInfo
from univis.domain.policy_episode import PolicyEpisode, PolicyEpisodeMetadata
from univis.preprocessors.base import EpisodePreprocessor


class ImageMaskPreprocessor(EpisodePreprocessor):
    """Black out camera frames for a given side during export."""

    def __init__(self, side: str) -> None:
        self.side = side  # "left" or "right"

    def info(self) -> ComponentInfo:
        return ComponentInfo(
            name=f"mask_{self.side}_image",
            label=f"Mask {self.side.title()} Image",
            description=f"Black out {self.side}-side camera frames during export.",
        )

    def preprocess_episode(self, episode: PolicyEpisode) -> PolicyEpisode:
        return episode  # image masking is adapter-level only

    def preprocess_adapter(self, adapter, metadata: PolicyEpisodeMetadata):
        masked = {cam.key for cam in metadata.cameras if self.side in cam.key}
        if not masked:
            return adapter
        dims = {cam.key: (cam.width, cam.height) for cam in metadata.cameras}
        return _MaskedImageAdapter(adapter, dims, masked)


class _MaskedImageAdapter:
    """Proxies an adapter but returns solid black frames for masked cameras.

    Does NOT inherit from RawEpisodeAdapter — uses __getattr__ delegation
    to avoid ABC instantiation issues. Only overrides the image-serving
    methods that matter for export.
    """

    def __init__(self, inner, dims: dict[str, tuple[int, int]], masked_keys: set[str]) -> None:
        self._inner = inner
        self._dims = dims
        self._masked = masked_keys
        self._black_cache: dict[str, ImageFrame] = {}

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def get_image_frame(self, episode_id, camera_key, frame_index, source=None):
        if camera_key in self._masked:
            return self._black_frame(camera_key)
        return self._inner.get_image_frame(episode_id, camera_key, frame_index, source)

    def get_image_frames(self, episode_id, camera_key, start_index, count, source=None):
        if camera_key in self._masked:
            black = self._black_frame(camera_key)
            return [black] * count
        return self._inner.get_image_frames(episode_id, camera_key, start_index, count, source)

    def clear_caches(self):
        self._inner.clear_caches()
        self._black_cache.clear()

    def _black_frame(self, camera_key: str) -> ImageFrame:
        if camera_key not in self._black_cache:
            w, h = self._dims.get(camera_key, (640, 480))
            buf = BytesIO()
            Image.new("RGB", (w, h), (0, 0, 0)).save(buf, format="PNG")
            self._black_cache[camera_key] = ImageFrame(data=buf.getvalue(), media_type="image/png")
        return self._black_cache[camera_key]
