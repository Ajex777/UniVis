"""Tests for local named workspace source flow."""

from pathlib import Path

from fastapi.testclient import TestClient

from hdf5_fixtures import write_script_hdf5
from pika_fixtures import write_pika_raw_episode
from univis.app import create_app, parse_output_arg, parse_workspace_args


def test_workspace_lists_children_and_activates_hdf5(tmp_path: Path) -> None:
    """Verify workspace browsing can activate a local HDF5 directory."""

    data_root = tmp_path / "data"
    hdf5_dir = data_root / "hdf5"
    hdf5_dir.mkdir(parents=True)
    write_script_hdf5(hdf5_dir / "episode1.hdf5")
    client = TestClient(create_app(workspaces={"data": data_root}))

    workspaces = client.get("/api/workspaces")
    assert workspaces.status_code == 200
    assert workspaces.json()[0]["name"] == "data"

    children = client.get("/api/workspaces/data/children")
    assert children.status_code == 200
    assert children.json()["entries"][0]["relative_path"] == "hdf5"

    activated = client.post(
        "/api/workspaces/source",
        json={
            "workspace": "data",
            "relative_path": "hdf5",
            "input_adapter": "HDF5EpisodeAdapter",
        },
    )
    assert activated.status_code == 200
    assert activated.json()["mode"] == "workspace"
    assert activated.json()["episodes"][0]["episode_id"] == "episode1"


def test_workspace_activates_pika_raw_without_upload(tmp_path: Path) -> None:
    """Verify PIKA raw data can be read directly from a workspace."""

    data_root = tmp_path / "raw"
    write_pika_raw_episode(data_root, frames=56)
    client = TestClient(create_app(workspaces={"raw": data_root}))

    activated = client.post(
        "/api/workspaces/source",
        json={
            "workspace": "raw",
            "relative_path": "",
            "input_adapter": "PikaRawEpisodeAdapter",
        },
    )
    assert activated.status_code == 200
    assert activated.json()["episodes"][0]["episode_id"] == "episode0"

    frame = client.get("/api/episodes/episode0/frame/cam_left_wrist/0")
    assert frame.status_code == 200
    assert frame.headers["content-type"].startswith("image/png")


def test_workspace_rejects_path_escape(tmp_path: Path) -> None:
    """Verify workspace API rejects relative paths that escape the root."""

    client = TestClient(create_app(workspaces={"data": tmp_path}))
    response = client.get("/api/workspaces/data/children", params={"path": "../"})

    assert response.status_code == 400
    assert "invalid workspace path" in response.json()["detail"]


def test_parse_workspace_args() -> None:
    """Verify CLI workspace parsing accepts repeated NAME=PATH specs."""

    parsed = parse_workspace_args(["raw=/tmp/raw", "hdf5=/tmp/hdf5"])

    assert parsed["raw"] == Path("/tmp/raw")
    assert parsed["hdf5"] == Path("/tmp/hdf5")


def test_parse_output_arg() -> None:
    """Verify CLI output parsing returns an optional export root."""

    assert parse_output_arg("") is None
    assert parse_output_arg("/tmp/exports") == Path("/tmp/exports")
