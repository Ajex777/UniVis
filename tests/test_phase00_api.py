"""Smoke tests for Phase 00 fake PolicyEpisode APIs."""

from fastapi.testclient import TestClient

from univis.app import create_app


def test_episode_list_and_metadata() -> None:
    """Verify episode list and metadata endpoints.

    Inputs:
        None. The test uses the default fake repository.
    Output:
        Assertions that API responses contain fake episode metadata.
    """

    client = TestClient(create_app())
    response = client.get("/api/episodes")
    assert response.status_code == 200
    episodes = response.json()
    assert len(episodes) >= 2

    episode_id = episodes[0]["episode_id"]
    meta_response = client.get(f"/api/episodes/{episode_id}/metadata")
    assert meta_response.status_code == 200
    metadata = meta_response.json()
    assert metadata["num_frames"] > 0
    assert len(metadata["cameras"]) >= 1


def test_trajectory_and_frame_endpoints() -> None:
    """Verify trajectory and generated camera frame endpoints.

    Inputs:
        None. The test fetches the first fake episode.
    Output:
        Assertions that trajectory JSON and SVG frame responses are available.
    """

    client = TestClient(create_app())
    episode = client.get("/api/episodes").json()[0]
    episode_id = episode["episode_id"]
    camera_key = episode["cameras"][0]["key"]

    trajectory_response = client.get(f"/api/episodes/{episode_id}/trajectory")
    assert trajectory_response.status_code == 200
    trajectory = trajectory_response.json()
    assert len(trajectory["left_xyz"]) == episode["num_frames"]
    assert len(trajectory["right_gripper"]) == episode["num_frames"]

    frame_response = client.get(f"/api/episodes/{episode_id}/frame/{camera_key}/0")
    assert frame_response.status_code == 200
    assert frame_response.headers["content-type"].startswith("image/svg+xml")
    assert "<svg" in frame_response.text


def test_annotation_update() -> None:
    """Verify in-memory annotation save behavior.

    Inputs:
        None. The test updates a fake episode annotation.
    Output:
        Assertions that the updated annotation is returned and persisted.
    """

    client = TestClient(create_app())
    episode_id = client.get("/api/episodes").json()[0]["episode_id"]
    payload = {
        "language_prompt": "updated instruction",
        "review_status": "accepted",
        "notes": "phase 00 smoke test",
        "quality_tags": ["ok"],
    }

    response = client.patch(f"/api/episodes/{episode_id}/annotation", json=payload)
    assert response.status_code == 200
    assert response.json()["language_prompt"] == "updated instruction"

    metadata = client.get(f"/api/episodes/{episode_id}/metadata").json()
    assert metadata["annotation"]["review_status"] == "accepted"


def test_registry_endpoint() -> None:
    """Verify adapter/exporter registry endpoint.

    Inputs:
        None. The test reads the fake Phase 001 registry.
    Output:
        Assertions that input adapters and output exporters are listed.
    """

    client = TestClient(create_app())
    response = client.get("/api/registry")
    assert response.status_code == 200
    payload = response.json()
    assert payload["input_adapters"][0]["name"] == "FakePolicyEpisodeAdapter"
    assert payload["output_exporters"][0]["name"] == "HDF5EpisodeExporter"
