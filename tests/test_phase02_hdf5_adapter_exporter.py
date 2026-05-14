"""Tests for Phase 02 HDF5 adapter and exporter."""

from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient

from univis.adapters.base import EpisodeSource
from univis.adapters.fake_policy_episode import FakePolicyEpisodeAdapter
from univis.adapters.hdf5 import HDF5EpisodeAdapter
from univis.app import create_app
from univis.exporters.hdf5 import HDF5EpisodeExporter
from univis.utils.hdf5_episode import frames_to_qpos


def test_policy_episode_hdf5_round_trip(tmp_path: Path) -> None:
    """Verify `PolicyEpisode -> HDF5 -> PolicyEpisode` round trip.

    Inputs:
        tmp_path: Temporary output directory.
    Output:
        Assertions that metadata, cameras, prompt, and qpos rows survive.
    """

    episode = FakePolicyEpisodeAdapter().load_episode("fake-dual")
    result = HDF5EpisodeExporter().export(episode, tmp_path)
    adapter = HDF5EpisodeAdapter()
    loaded = adapter.load_episode(
        episode.metadata.episode_id,
        EpisodeSource(root_path=tmp_path),
    )

    assert result.success is True
    assert loaded.metadata.num_frames == episode.metadata.num_frames
    assert [cam.key for cam in loaded.metadata.cameras] == [
        cam.key for cam in episode.metadata.cameras
    ]
    assert loaded.metadata.annotation.language_prompt == (
        episode.metadata.annotation.language_prompt
    )
    np.testing.assert_allclose(frames_to_qpos(loaded.frames), frames_to_qpos(episode.frames))


def test_hdf5_adapter_lists_directory_naturally(tmp_path: Path) -> None:
    """Verify HDF5 metadata listing uses natural episode order.

    Inputs:
        tmp_path: Temporary output directory.
    Output:
        Assertions that episode2 sorts before episode10.
    """

    fake = FakePolicyEpisodeAdapter().load_episode("fake-single")
    exporter = HDF5EpisodeExporter()
    for episode_id in ("episode10", "episode2"):
        episode = fake.model_copy(deep=True)
        episode.metadata.episode_id = episode_id
        exporter.export(episode, tmp_path)

    items = HDF5EpisodeAdapter().list_metadata(EpisodeSource(root_path=tmp_path))
    assert [item.episode_id for item in items] == ["episode2", "episode10"]


def test_hdf5_language_prompt_writeback(tmp_path: Path) -> None:
    """Verify HDF5 language prompt can be updated in place.

    Inputs:
        tmp_path: Temporary output directory.
    Output:
        Assertions that reloaded metadata sees the new prompt.
    """

    episode = FakePolicyEpisodeAdapter().load_episode("fake-single")
    result = HDF5EpisodeExporter().export(episode, tmp_path)
    path = Path(result.output_path)

    adapter = HDF5EpisodeAdapter()
    adapter.write_language_prompt(path, "updated hdf5 prompt")
    loaded = adapter.load_episode(episode.metadata.episode_id, EpisodeSource(root_path=path))

    assert loaded.metadata.annotation.language_prompt == "updated hdf5 prompt"


def test_api_can_switch_to_hdf5_source(tmp_path: Path) -> None:
    """Verify viewer APIs can use HDF5EpisodeAdapter as active source.

    Inputs:
        tmp_path: Temporary output directory for generated HDF5.
    Output:
        Assertions that source switching, trajectory, frames, and annotation
        update work through the common API endpoints.
    """

    episode = FakePolicyEpisodeAdapter().load_episode("fake-dual")
    HDF5EpisodeExporter().export(episode, tmp_path)
    client = TestClient(create_app())

    response = client.post(
        "/api/source",
        json={"input_adapter": "HDF5EpisodeAdapter", "root_path": str(tmp_path)},
    )
    assert response.status_code == 200
    assert response.json()["episodes"][0]["episode_id"] == episode.metadata.episode_id

    trajectory = client.get(f"/api/episodes/{episode.metadata.episode_id}/trajectory")
    assert trajectory.status_code == 200
    assert len(trajectory.json()["left_xyz"]) == episode.metadata.num_frames

    camera_key = episode.metadata.cameras[0].key
    frame = client.get(f"/api/episodes/{episode.metadata.episode_id}/frame/{camera_key}/0")
    assert frame.status_code == 200
    assert frame.headers["content-type"].startswith("image/svg+xml")

    updated = client.patch(
        f"/api/episodes/{episode.metadata.episode_id}/annotation",
        json={
            "language_prompt": "api hdf5 prompt",
            "review_status": "accepted",
            "notes": "saved via api",
            "quality_tags": ["hdf5"],
        },
    )
    assert updated.status_code == 200
    metadata = client.get(f"/api/episodes/{episode.metadata.episode_id}/metadata")
    assert metadata.json()["annotation"]["language_prompt"] == "api hdf5 prompt"


def test_api_can_upload_hdf5_directory_and_scan(tmp_path: Path) -> None:
    """Verify browser-style HDF5 upload switches the active viewer source.

    Inputs:
        tmp_path: Temporary directory for generated HDF5 and upload staging.
    Output:
        Assertions that upload session, file staging, completion, and viewer
        metadata loading work together.
    """

    source_dir = tmp_path / "source"
    upload_root = tmp_path / "uploads"
    episode = FakePolicyEpisodeAdapter().load_episode("fake-single")
    result = HDF5EpisodeExporter().export(episode, source_dir)
    hdf5_path = Path(result.output_path)
    client = TestClient(create_app(uploads_root=upload_root))

    created = client.post(
        "/api/uploads/datasets",
        json={
            "input_adapter": "HDF5EpisodeAdapter",
            "root_label": "selected_hdf5",
            "file_count": 1,
            "total_size": hdf5_path.stat().st_size,
        },
    )
    assert created.status_code == 200
    upload_id = created.json()["upload_id"]

    with hdf5_path.open("rb") as file_obj:
        uploaded = client.post(
            f"/api/uploads/{upload_id}/files",
            data={"relative_paths": f"selected_hdf5/{hdf5_path.name}"},
            files={"files": (hdf5_path.name, file_obj, "application/octet-stream")},
        )
    assert uploaded.status_code == 200
    assert uploaded.json()["received_files"] == 1

    completed = client.post(f"/api/uploads/{upload_id}/complete")
    assert completed.status_code == 200
    episodes = completed.json()["episodes"]
    assert episodes[0]["episode_id"] == episode.metadata.episode_id

    metadata = client.get(f"/api/episodes/{episode.metadata.episode_id}/metadata")
    assert metadata.status_code == 200
    assert metadata.json()["annotation"]["language_prompt"] == (
        episode.metadata.annotation.language_prompt
    )
