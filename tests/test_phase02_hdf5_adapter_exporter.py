"""Tests for Phase 02 HDF5 adapter and exporter."""

from io import BytesIO
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from univis.adapters.base import EpisodeSource
from univis.adapters.hdf5 import HDF5EpisodeAdapter
from univis.app import create_app
from univis.exporters.hdf5 import HDF5EpisodeExporter
from univis.utils.hdf5_episode import frames_to_qpos
from hdf5_fixtures import export_compressed_hdf5, make_episode, write_script_hdf5


def test_policy_episode_hdf5_round_trip(tmp_path: Path) -> None:
    """Verify `PolicyEpisode -> HDF5 -> PolicyEpisode` round trip.

    Inputs:
        tmp_path: Temporary output directory.
    Output:
        Assertions that metadata, cameras, prompt, and qpos rows survive.
    """

    episode = make_episode("round-trip")
    result = export_compressed_hdf5(episode, tmp_path)
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

    base_episode = make_episode()
    for episode_id in ("episode10", "episode2"):
        episode = base_episode.model_copy(deep=True)
        episode.metadata.episode_id = episode_id
        export_compressed_hdf5(episode, tmp_path)

    items = HDF5EpisodeAdapter().list_metadata(EpisodeSource(root_path=tmp_path))
    assert [item.episode_id for item in items] == ["episode2", "episode10"]


def test_hdf5_source_validation_rejects_empty_and_nested_dirs(tmp_path: Path) -> None:
    """Verify HDF5 adapter validates single-level directory layout."""

    adapter = HDF5EpisodeAdapter()
    empty = tmp_path / "empty"
    nested = tmp_path / "nested"
    empty.mkdir()
    (nested / "child").mkdir(parents=True)
    write_script_hdf5(nested / "child" / "episode_nested.hdf5")

    empty_result = adapter.validate_source(EpisodeSource(root_path=empty))
    nested_result = adapter.validate_source(EpisodeSource(root_path=nested))

    assert empty_result.valid is False
    assert "top level" in empty_result.message
    assert nested_result.valid is False
    assert "one directory level" in nested_result.message


def test_source_validation_api_does_not_switch_source(tmp_path: Path) -> None:
    """Verify validation can run before source switching."""

    hdf5_path = tmp_path / "valid_episode.hdf5"
    write_script_hdf5(hdf5_path)
    client = TestClient(create_app())

    valid = client.post(
        "/api/source/validate",
        json={"input_adapter": "HDF5EpisodeAdapter", "root_path": str(tmp_path)},
    )
    assert valid.status_code == 200
    assert valid.json()["valid"] is True
    assert valid.json()["episode_count"] == 1

    assert client.get("/api/episodes").json() == []


def test_hdf5_language_prompt_writeback(tmp_path: Path) -> None:
    """Verify HDF5 language prompt can be updated in place.

    Inputs:
        tmp_path: Temporary output directory.
    Output:
        Assertions that reloaded metadata sees the new prompt.
    """

    episode = make_episode("prompt-test")
    result = export_compressed_hdf5(episode, tmp_path)
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

    hdf5_path = tmp_path / "script_episode.hdf5"
    write_script_hdf5(hdf5_path)
    client = TestClient(create_app())

    response = client.post(
        "/api/source",
        json={"input_adapter": "HDF5EpisodeAdapter", "root_path": str(tmp_path)},
    )
    assert response.status_code == 200
    episode_id = response.json()["episodes"][0]["episode_id"]
    assert episode_id == "script_episode"

    trajectory = client.get(f"/api/episodes/{episode_id}/trajectory")
    assert trajectory.status_code == 200
    assert len(trajectory.json()["left_xyz"]) == 4

    frame = client.get(f"/api/episodes/{episode_id}/frame/cam_left_wrist/2")
    assert frame.status_code == 200
    assert frame.headers["content-type"].startswith("image/")
    image = Image.open(BytesIO(frame.content)).convert("RGB")
    assert image.size == (8, 6)
    assert image.getpixel((0, 0)) == pytest.approx((60, 42, 22), abs=5)

    updated = client.patch(
        f"/api/episodes/{episode_id}/annotation",
        json={
            "language_prompt": "api hdf5 prompt",
            "review_status": "accepted",
            "notes": "saved via api",
            "quality_tags": ["hdf5"],
        },
    )
    assert updated.status_code == 200
    metadata = client.get(f"/api/episodes/{episode_id}/metadata")
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
    source_dir.mkdir()
    hdf5_path = source_dir / "uploaded_script_episode.hdf5"
    write_script_hdf5(hdf5_path)
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
    assert episodes[0]["episode_id"] == "uploaded_script_episode"

    metadata = client.get("/api/episodes/uploaded_script_episode/metadata")
    assert metadata.status_code == 200
    assert metadata.json()["annotation"]["language_prompt"] == "script compatible prompt"

    frame = client.get("/api/episodes/uploaded_script_episode/frame/cam_right_wrist/1")
    assert frame.status_code == 200
    assert frame.headers["content-type"].startswith("image/")


def test_upload_rejects_input_format_mismatch(tmp_path: Path) -> None:
    """Verify upload completion rejects non-HDF5 source for HDF5 adapter."""

    source_file = tmp_path / "notes.txt"
    source_file.write_text("not hdf5", encoding="utf-8")
    client = TestClient(create_app(uploads_root=tmp_path / "uploads"))

    created = client.post(
        "/api/uploads/datasets",
        json={
            "input_adapter": "HDF5EpisodeAdapter",
            "root_label": "bad_upload",
            "file_count": 1,
            "total_size": source_file.stat().st_size,
        },
    )
    upload_id = created.json()["upload_id"]
    with source_file.open("rb") as file_obj:
        uploaded = client.post(
            f"/api/uploads/{upload_id}/files",
            data={"relative_paths": f"bad_upload/{source_file.name}"},
            files={"files": (source_file.name, file_obj, "text/plain")},
        )
    assert uploaded.status_code == 200

    completed = client.post(f"/api/uploads/{upload_id}/complete")
    assert completed.status_code == 400
    assert "HDF5 source" in completed.json()["detail"]
