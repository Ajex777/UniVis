"""Tests for raw review to HDF5 conversion workflow."""

from io import BytesIO
from pathlib import Path
import time

from fastapi.testclient import TestClient
from PIL import Image

from pika_fixtures import write_pika_raw_episode
from univis.adapters.base import EpisodeSource
from univis.adapters.hdf5 import HDF5EpisodeAdapter
from univis.app import create_app


def test_raw_annotation_review_and_single_hdf5_conversion(tmp_path: Path) -> None:
    """Verify UI-facing raw annotation can be exported to HDF5."""

    raw_root = tmp_path / "raw"
    output_root = tmp_path / "out"
    write_pika_raw_episode(raw_root, frames=56)
    client = TestClient(create_app(workspaces={"raw": raw_root}, output_root=output_root))

    activated = client.post(
        "/api/workspaces/source",
        json={
            "workspace": "raw",
            "relative_path": "",
            "input_adapter": "PikaRawEpisodeAdapter",
        },
    )
    episode_id = activated.json()["episodes"][0]["episode_id"]

    saved = client.patch(
        f"/api/episodes/{episode_id}/annotation",
        json={
            "language_prompt": "place the book on the shelf",
            "review_status": "accepted",
            "notes": "clean trajectory",
            "quality_tags": ["good"],
        },
    )
    assert saved.status_code == 200
    assert saved.json()["review_status"] == "accepted"

    converted = client.post(
        f"/api/conversions/episodes/{episode_id}",
        json={"exporter_name": "HDF5EpisodeExporter", "output_subpath": "reviewed"},
    )
    assert converted.status_code == 200
    job = wait_job(client, converted.json()["job_id"])
    assert job["succeeded"] == 1
    assert Path(job["items"][0]["output_path"]).exists()

    adapter = HDF5EpisodeAdapter()
    source = EpisodeSource(root_path=output_root / "reviewed")
    exported = adapter.load_episode(episode_id, source)
    metadata = client.get(f"/api/episodes/{episode_id}/metadata").json()
    trajectory = client.get(f"/api/episodes/{episode_id}/trajectory").json()

    assert exported.metadata.annotation.language_prompt == "place the book on the shelf"
    assert exported.metadata.annotation.review_status == "accepted"
    assert exported.metadata.annotation.notes == "clean trajectory"
    assert exported.metadata.num_frames == metadata["num_frames"]
    assert len(trajectory["left_xyz"]) == exported.metadata.num_frames

    frame = adapter.get_image_frame(episode_id, "cam_left_wrist", 0, source)
    image = Image.open(BytesIO(frame.data)).convert("RGB")
    assert image.size == (8, 6)


def test_accepted_batch_conversion_skips_pending(tmp_path: Path) -> None:
    """Verify batch conversion only exports accepted active episodes."""

    raw_root = tmp_path / "raw"
    output_root = tmp_path / "out"
    write_pika_raw_episode(raw_root, episode_name="episode0", frames=56)
    write_pika_raw_episode(raw_root, episode_name="episode1", frames=56)
    client = TestClient(create_app(workspaces={"raw": raw_root}, output_root=output_root))

    activated = client.post(
        "/api/workspaces/source",
        json={
            "workspace": "raw",
            "relative_path": "",
            "input_adapter": "PikaRawEpisodeAdapter",
        },
    )
    assert len(activated.json()["episodes"]) == 2
    client.patch(
        "/api/episodes/episode1/annotation",
        json={"language_prompt": "accepted only", "review_status": "accepted"},
    )

    converted = client.post(
        "/api/conversions/accepted",
        json={"exporter_name": "HDF5EpisodeExporter", "output_subpath": "accepted"},
    )
    assert converted.status_code == 200
    job = wait_job(client, converted.json()["job_id"])

    assert job["total"] == 1
    assert job["items"][0]["episode_id"] == "episode1"
    assert (output_root / "accepted" / "conversion_report.json").exists()
    episodes = HDF5EpisodeAdapter().list_metadata(EpisodeSource(root_path=output_root / "accepted"))
    assert [episode.episode_id for episode in episodes] == ["episode1"]


def test_conversion_output_subpath_stays_under_configured_root(tmp_path: Path) -> None:
    """Verify conversion output paths are resolved under the CLI output root."""

    client = TestClient(create_app(output_root=tmp_path / "exports"))
    config = client.get("/api/conversions/config")
    assert config.status_code == 200
    assert config.json()["root"] == str((tmp_path / "exports").resolve())

    response = client.post(
        "/api/conversions/accepted",
        json={"exporter_name": "HDF5EpisodeExporter", "output_subpath": "../escape"},
    )
    assert response.status_code == 400
    assert "cannot contain '..'" in response.json()["detail"]


def wait_job(client: TestClient, job_id: str, timeout: float = 5.0) -> dict:
    """Poll one conversion job until it reaches a terminal state."""

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get(f"/api/conversions/jobs/{job_id}")
        assert response.status_code == 200
        payload = response.json()
        if payload["status"] in {"succeeded", "failed"}:
            return payload
        time.sleep(0.05)
    raise AssertionError(f"conversion job did not finish: {job_id}")
