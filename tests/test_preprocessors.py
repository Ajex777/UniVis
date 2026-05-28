"""Tests for the EpisodePreprocessor layer."""

from io import BytesIO

import pytest
from PIL import Image

from univis.adapters.base import ImageFrame, RawEpisodeAdapter
from univis.core.components import ComponentInfo
from univis.domain.policy_episode import (
    Annotation,
    ArmFrame,
    CameraStream,
    PolicyEpisode,
    PolicyEpisodeMetadata,
    PolicyFrame,
)
from univis.preprocessors import load_preprocessors
from univis.preprocessors.action_mask import ActionMaskPreprocessor
from univis.preprocessors.image_mask import ImageMaskPreprocessor, _MaskedImageAdapter


def _episode(num_frames=3):
    """Build a minimal 2-camera episode for testing."""
    cameras = [
        CameraStream(key="cam_left_wrist", label="Left Wrist", width=320, height=240),
        CameraStream(key="cam_right_wrist", label="Right Wrist", width=640, height=480),
    ]
    frames = [
        PolicyFrame(
            index=i,
            timestamp=float(i),
            left=ArmFrame(xyz=[1, 2, 3], rot6d=[1, 0, 0, 0, 1, 0], gripper=0.8),
            right=ArmFrame(xyz=[4, 5, 6], rot6d=[0, 1, 0, 0, 0, 1], gripper=0.5),
        )
        for i in range(num_frames)
    ]
    meta = PolicyEpisodeMetadata(
        episode_id="test_ep",
        title="Test Episode",
        num_frames=num_frames,
        fps=10.0,
        cameras=cameras,
        annotation=Annotation(),
    )
    return PolicyEpisode(metadata=meta, frames=frames)


class _FakeAdapter(RawEpisodeAdapter):
    """Adapter that returns a fixed image for any request."""

    def __init__(self):
        buf = BytesIO()
        Image.new("RGB", (64, 48), (255, 0, 0)).save(buf, format="PNG")
        self._frame = ImageFrame(data=buf.getvalue(), media_type="image/png")

    @classmethod
    def info(cls):
        return ComponentInfo(name="FakeAdapter", label="Fake")

    def list_metadata(self, source=None):
        return []

    def load_episode(self, episode_id, source=None):
        raise NotImplementedError

    def get_image_frame(self, episode_id, camera_key, frame_index, source=None):
        return self._frame

    def get_image_frames(self, episode_id, camera_key, start_index, count, source=None):
        return [self._frame] * count

    def clear_caches(self):
        pass


# ── Action mask ──────────────────────────────────────────────

def test_action_mask_left():
    ep = _episode(2)
    pp = ActionMaskPreprocessor("left")
    result = pp.preprocess_episode(ep)
    for f in result.frames:
        assert f.left.xyz == [0, 0, 0]
        assert f.left.rot6d == [1, 0, 0, 0, 1, 0]
        assert f.left.gripper == 1.0
        assert f.right == ep.frames[0].right  # unchanged


def test_action_mask_right():
    ep = _episode(2)
    pp = ActionMaskPreprocessor("right")
    result = pp.preprocess_episode(ep)
    for f in result.frames:
        assert f.right.xyz == [0, 0, 0]
        assert f.right.rot6d == [1, 0, 0, 0, 1, 0]
        assert f.right.gripper == 1.0
        assert f.left == ep.frames[0].left  # unchanged


def test_action_mask_idempotent():
    ep = _episode(2)
    pp = ActionMaskPreprocessor("left")
    once = pp.preprocess_episode(ep)
    twice = pp.preprocess_episode(once)
    for f1, f2 in zip(once.frames, twice.frames):
        assert f1.left == f2.left
        assert f1.right == f2.right


def test_action_mask_preserves_metadata():
    ep = _episode(2)
    pp = ActionMaskPreprocessor("left")
    result = pp.preprocess_episode(ep)
    assert result.metadata == ep.metadata
    assert len(result.frames) == len(ep.frames)


# ── Image mask ────────────────────────────────────────────────

def test_image_mask_black_frame():
    adapter = _FakeAdapter()
    ep = _episode(2)
    pp = ImageMaskPreprocessor("left")
    wrapped = pp.preprocess_adapter(adapter, ep.metadata)

    frame = wrapped.get_image_frame("test_ep", "cam_left_wrist", 0)
    img = Image.open(BytesIO(frame.data))
    assert img.size == (320, 240)
    assert img.getpixel((10, 10)) == (0, 0, 0)

    # right camera still returns original red frame
    frame_r = wrapped.get_image_frame("test_ep", "cam_right_wrist", 0)
    img_r = Image.open(BytesIO(frame_r.data))
    assert img_r.getpixel((10, 10)) == (255, 0, 0)


def test_image_mask_no_matching_camera():
    adapter = _FakeAdapter()
    ep = _episode(2)
    # Rename cameras so "left" substring won't match
    ep.metadata.cameras[0].key = "cam_forward"
    ep.metadata.cameras[1].key = "cam_top"
    pp = ImageMaskPreprocessor("left")
    wrapped = pp.preprocess_adapter(adapter, ep.metadata)
    assert wrapped is adapter  # returns original, unwrapped


def test_image_mask_batch():
    adapter = _FakeAdapter()
    ep = _episode(2)
    pp = ImageMaskPreprocessor("right")
    wrapped = pp.preprocess_adapter(adapter, ep.metadata)

    frames = wrapped.get_image_frames("test_ep", "cam_right_wrist", 0, 3)
    assert len(frames) == 3
    for f in frames:
        img = Image.open(BytesIO(f.data))
        assert img.getpixel((10, 10)) == (0, 0, 0)


def test_image_mask_clear_caches():
    adapter = _FakeAdapter()
    ep = _episode(2)
    pp = ImageMaskPreprocessor("left")
    wrapped = pp.preprocess_adapter(adapter, ep.metadata)

    wrapped.clear_caches()  # should not raise
    # after clear, subsequent frame requests still work
    frame = wrapped.get_image_frame("test_ep", "cam_left_wrist", 0)
    assert frame.media_type == "image/png"


# ── Chain composition ─────────────────────────────────────────

def test_chain_both_actions():
    ep = _episode(2)
    pp_left = ActionMaskPreprocessor("left")
    pp_right = ActionMaskPreprocessor("right")

    result = pp_left.preprocess_episode(ep)
    result = pp_right.preprocess_episode(result)
    for f in result.frames:
        assert f.left.xyz == [0, 0, 0]
        assert f.right.xyz == [0, 0, 0]


def test_chain_image_preprocess_episode_is_identity():
    ep = _episode(2)
    pp = ImageMaskPreprocessor("left")
    result = pp.preprocess_episode(ep)
    assert result == ep  # no modification


# ── Component info ────────────────────────────────────────────

def test_action_mask_info():
    pp = ActionMaskPreprocessor("left")
    info = pp.info()
    assert info.name == "mask_left_action"
    assert "Left" in info.label

    pp_r = ActionMaskPreprocessor("right")
    assert pp_r.info().name == "mask_right_action"


def test_image_mask_info():
    pp = ImageMaskPreprocessor("left")
    assert pp.info().name == "mask_left_image"


# ── Factory ───────────────────────────────────────────────────

def test_load_preprocessors():
    pps = load_preprocessors()
    names = {pp.info().name for pp in pps}
    assert names == {
        "mask_left_action",
        "mask_right_action",
        "mask_left_image",
        "mask_right_image",
    }


# ── Registry integration ──────────────────────────────────────

def test_registry_includes_preprocessors():
    from univis.core.components import ComponentRegistry

    pps = load_preprocessors()
    reg = ComponentRegistry(preprocessors=pps)
    payload = reg.api_payload()
    assert "preprocessors" in payload
    assert len(payload["preprocessors"]) == 4
    assert payload["preprocessors"][0]["name"] == "mask_left_action"
