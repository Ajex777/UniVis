"""Tests for batched camera frame APIs."""

from pathlib import Path

from fastapi.testclient import TestClient

from hdf5_fixtures import write_script_hdf5
from univis.app import create_app


def test_api_returns_frame_batches_for_prefetch(tmp_path: Path) -> None:
    """Verify frame batch API returns contiguous base64 PNG payloads."""

    write_script_hdf5(tmp_path / "episode_batch.hdf5")
    client = TestClient(create_app())
    source = client.post(
        "/api/source",
        json={"input_adapter": "HDF5EpisodeAdapter", "root_path": str(tmp_path)},
    )
    assert source.status_code == 200

    batch = client.get("/api/episodes/episode_batch/frames/cam_left_wrist?start=1&count=3")
    assert batch.status_code == 200
    payload = batch.json()
    assert payload["start"] == 1
    assert payload["count"] == 3
    assert [frame["index"] for frame in payload["frames"]] == [1, 2, 3]
    assert payload["frames"][0]["media_type"].startswith("image/")
    assert len(payload["frames"][0]["data"]) > 0
