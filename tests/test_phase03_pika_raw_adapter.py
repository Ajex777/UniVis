"""Tests for Phase 03 PIKA raw adapter."""

from io import BytesIO
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient
from PIL import Image

from pika_fixtures import write_pika_raw_episode
from univis.adapters.base import EpisodeSource
from univis.adapters.pika_manifest import scan_pika_episode
from univis.adapters.pika_raw import PikaRawEpisodeAdapter
from univis.adapters.pika_sync import PikaSyncOptions
from univis.app import create_app
from univis.domain.policy_episode import Annotation
from univis.utils.hdf5_episode import frames_to_qpos


def test_pika_raw_adapter_loads_policy_episode(tmp_path: Path) -> None:
    """Verify a PIKA raw episode becomes a synchronized PolicyEpisode."""

    episode_dir = write_pika_raw_episode(tmp_path, frames=8)
    adapter = PikaRawEpisodeAdapter(PikaSyncOptions(min_frames=3))
    episode = adapter.load_episode("episode0", EpisodeSource(root_path=tmp_path))

    assert episode.metadata.episode_id == "episode0"
    assert episode.metadata.annotation.language_prompt == "raw prompt"
    assert [camera.key for camera in episode.metadata.cameras] == [
        "cam_left_wrist",
        "cam_right_wrist",
    ]
    assert episode.metadata.num_frames == 6
    assert len(episode.frames) == episode.metadata.num_frames
    np.testing.assert_allclose(
        frames_to_qpos(episode.frames),
        adapter.synchronizer.synchronize(scan_pika_episode(episode_dir)).qpos,
    )


def test_pika_raw_adapter_serves_image_and_writes_instruction(tmp_path: Path) -> None:
    """Verify frame preview and `instructions.json` writeback."""

    write_pika_raw_episode(tmp_path, frames=8)
    adapter = PikaRawEpisodeAdapter(PikaSyncOptions(min_frames=3))
    source = EpisodeSource(root_path=tmp_path)

    frame = adapter.get_image_frame("episode0", "cam_left_wrist", 0, source)
    image = Image.open(BytesIO(frame.data)).convert("RGB")
    assert frame.media_type == "image/png"
    assert image.size == (8, 6)

    saved = adapter.update_annotation(
        "episode0",
        Annotation(language_prompt="updated raw prompt", review_status="accepted"),
        source,
    )
    assert saved.language_prompt == "updated raw prompt"
    reloaded = adapter.load_episode("episode0", source)
    assert reloaded.metadata.annotation.language_prompt == "updated raw prompt"


def test_api_can_upload_and_view_pika_raw_directory(tmp_path: Path) -> None:
    """Verify browser-style upload can activate PIKA raw data."""

    source_dir = tmp_path / "selected_raw"
    episode_dir = write_pika_raw_episode(source_dir, frames=56)
    files = sorted(path for path in source_dir.rglob("*") if path.is_file())
    client = TestClient(create_app(uploads_root=tmp_path / "uploads"))

    created = client.post(
        "/api/uploads/datasets",
        json={
            "input_adapter": "PikaRawEpisodeAdapter",
            "root_label": "selected_raw",
            "file_count": len(files),
            "total_size": sum(path.stat().st_size for path in files),
        },
    )
    assert created.status_code == 200
    upload_id = created.json()["upload_id"]

    upload_files = []
    try:
        for path in files:
            rel = path.relative_to(source_dir.parent).as_posix()
            upload_files.append(("files", (path.name, path.open("rb"), "application/octet-stream")))
            upload_files.append(("relative_paths", (None, rel)))
        uploaded = client.post(f"/api/uploads/{upload_id}/files", files=upload_files)
    finally:
        for item in upload_files:
            if item[0] == "files":
                item[1][1].close()
    assert uploaded.status_code == 200

    completed = client.post(f"/api/uploads/{upload_id}/complete")
    assert completed.status_code == 200
    assert completed.json()["episodes"][0]["episode_id"] == episode_dir.name

    trajectory = client.get(f"/api/episodes/{episode_dir.name}/trajectory")
    assert trajectory.status_code == 200
    assert len(trajectory.json()["left_xyz"]) >= 50

    frame = client.get(f"/api/episodes/{episode_dir.name}/frame/cam_right_wrist/0")
    assert frame.status_code == 200
    assert frame.headers["content-type"].startswith("image/png")
