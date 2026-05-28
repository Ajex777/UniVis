"""Tests for persistent upload-backed source selection."""

from pathlib import Path

from fastapi.testclient import TestClient

from hdf5_fixtures import write_script_hdf5
from univis.app import create_app


def test_completed_upload_can_be_reselected_after_restart(tmp_path: Path) -> None:
    """Verify completed uploads are persisted and can be activated later."""

    source_dir = tmp_path / "source"
    upload_root = tmp_path / "uploads"
    source_dir.mkdir()
    hdf5_path = source_dir / "episode_saved.hdf5"
    write_script_hdf5(hdf5_path)

    first_client = TestClient(create_app(uploads_root=upload_root))
    created = first_client.post(
        "/api/uploads/datasets",
        json={
            "input_adapter": "HDF5EpisodeAdapter",
            "root_label": "pos1",
            "file_count": 1,
            "total_size": hdf5_path.stat().st_size,
        },
    )
    upload_id = created.json()["upload_id"]
    with hdf5_path.open("rb") as file_obj:
        uploaded = first_client.post(
            f"/api/uploads/{upload_id}/files",
            data={"relative_paths": f"pos1/{hdf5_path.name}"},
            files={"files": (hdf5_path.name, file_obj, "application/octet-stream")},
        )
    assert uploaded.status_code == 200
    assert first_client.post(f"/api/uploads/{upload_id}/complete").status_code == 200

    restarted_client = TestClient(create_app(uploads_root=upload_root))
    sources = restarted_client.get("/api/uploads/sources")
    assert sources.status_code == 200
    assert sources.json()[0]["upload_id"] == upload_id
    assert sources.json()[0]["root_label"] == "pos1"
    assert restarted_client.get("/api/episodes").json() == []

    activated = restarted_client.post(f"/api/uploads/sources/{upload_id}/activate")
    assert activated.status_code == 200
    assert activated.json()["episodes"][0]["episode_id"] == "episode_saved"
