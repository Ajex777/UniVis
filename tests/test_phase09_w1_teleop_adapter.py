"""Tests for Dexforce W1 teleop adapter."""

from dataclasses import replace
from io import BytesIO
from pathlib import Path

import numpy as np
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from univis.adapters.base import EpisodeSource
from univis.api.routes import Phase00Router
from univis.core.components import ComponentRegistry
from univis.core.episode_session import EpisodeSession
from univis.formats.dexforce_w1_teleop.adapter import DexforceW1TeleopAdapter
from univis.formats.dexforce_w1_teleop.fk import W1FKBatchResult
from univis.formats.dexforce_w1_teleop.settings import W1TeleopConfig
from w1_fixtures import write_w1_teleop_episode


class FakeW1FK:
    """Fake FK that proves the adapter passes full qpos including waist."""

    def __init__(self) -> None:
        self.last_qpos: np.ndarray | None = None

    def compute_dual_arm_eef_batch(self, full_qpos: np.ndarray) -> W1FKBatchResult:
        """Return deterministic pose rows derived from full qpos."""

        self.last_qpos = np.asarray(full_qpos, dtype=np.float32)
        waist = self.last_qpos[:, 3]
        zeros = np.zeros_like(waist)
        left = np.stack([waist, zeros, zeros, np.ones_like(waist), zeros, zeros, zeros, np.ones_like(waist), zeros], axis=1)
        right = np.stack([zeros, waist, zeros, np.ones_like(waist), zeros, zeros, zeros, np.ones_like(waist), zeros], axis=1)
        return W1FKBatchResult(left=left.astype(np.float32), right=right.astype(np.float32))


class ExplodingFK:
    """FK helper that fails so API traceback payload can be asserted."""

    def compute_dual_arm_eef_batch(self, full_qpos: np.ndarray) -> W1FKBatchResult:
        """Raise when called by metadata/trajectory paths."""

        raise AssertionError("intentional W1 FK failure")


def test_w1_default_config_loads_has_waist() -> None:
    """Verify W1 config exposes full-qpos and FK options."""

    config = W1TeleopConfig.load()

    assert config.kinematics.has_waist is True
    assert config.waist_joint_names == ("WAIST",)
    assert config.left_arm.joint_names[0] == "LEFT_J1"
    assert len(config.joint_order) == 34


def test_w1_adapter_loads_policy_episode_from_full_qpos(tmp_path: Path) -> None:
    """Verify W1 adapter synchronizes qpos and calls FK with full qpos."""

    write_w1_teleop_episode(tmp_path, frames=6)
    config = _small_config()
    fk = FakeW1FK()
    adapter = DexforceW1TeleopAdapter(config=config, fk=fk)
    episode = adapter.load_episode("session0", EpisodeSource(root_path=tmp_path))

    assert episode.metadata.episode_id == "session0"
    assert episode.metadata.annotation.language_prompt == "w1 prompt"
    assert episode.metadata.num_frames == 6
    assert [camera.key for camera in episode.metadata.cameras] == [
        "camera_head_left", "camera_head_right", "camera_hand_left", "camera_hand_right",
    ]
    assert fk.last_qpos is not None
    assert fk.last_qpos.shape == (6, 34)
    assert episode.frames[0].left.xyz == [0.5, 0.0, 0.0]
    assert episode.frames[0].right.xyz == [0.0, 0.5, 0.0]
    assert episode.frames[-1].left.gripper == 1.0
    assert episode.frames[-1].right.gripper == 0.0


def test_w1_metadata_error_response_includes_traceback(tmp_path: Path) -> None:
    """Verify metadata load errors return message plus traceback to the browser."""

    write_w1_teleop_episode(tmp_path, frames=6)
    adapter = DexforceW1TeleopAdapter(config=_small_config(), fk=ExplodingFK())
    session = EpisodeSession([adapter], "DexforceW1TeleopAdapter")
    session.set_source("DexforceW1TeleopAdapter", str(tmp_path))
    app = FastAPI()
    app.include_router(
        Phase00Router(
            session,
            ComponentRegistry(input_adapters=[adapter]),
        ).router
    )

    response = TestClient(app).get("/api/episodes/session0/metadata")
    detail = response.json()["detail"]

    assert response.status_code == 400
    assert detail["message"] == "intentional W1 FK failure"
    assert "Traceback" in detail["traceback"]
    assert "compute_dual_arm_eef_batch" in detail["traceback"]


def test_w1_adapter_serves_image_frame(tmp_path: Path) -> None:
    """Verify W1 adapter serves original camera frames."""

    write_w1_teleop_episode(tmp_path, frames=6)
    adapter = DexforceW1TeleopAdapter(config=_small_config(), fk=FakeW1FK())
    frame = adapter.get_image_frame("session0", "camera_head_left", 0, EpisodeSource(root_path=tmp_path))
    image = Image.open(BytesIO(frame.data)).convert("RGB")

    assert frame.media_type == "image/png"
    assert image.size == (9, 7)


def _small_config() -> W1TeleopConfig:
    """Return default W1 config with a small test min frame count."""

    config = W1TeleopConfig.load()
    return replace(config, sync=replace(config.sync, min_frames=3))
