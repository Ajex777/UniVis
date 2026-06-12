"""Smoke tests for API startup without built-in sample data."""

from fastapi.testclient import TestClient

from univis.app import create_app


def test_initial_episode_list_is_empty_until_source_selected() -> None:
    """Verify startup waits for a real source."""

    client = TestClient(create_app())
    response = client.get("/api/episodes")

    assert response.status_code == 200
    assert response.json() == []


def test_registry_endpoint_lists_real_input_adapters() -> None:
    """Verify registry exposes registered real input adapters."""

    client = TestClient(create_app())
    response = client.get("/api/registry")

    assert response.status_code == 200
    payload = response.json()
    assert [item["name"] for item in payload["input_adapters"]] == [
        "HDF5EpisodeAdapter",
        "LeRobotV3EpisodeAdapter",
        "PikaRawEpisodeAdapter",
        "DexforceW1TeleopAdapter",
    ]
    assert payload["input_adapters"][0]["aliases"] == ["HDF5"]
    assert payload["input_adapters"][1]["aliases"] == ["LeRobotV3"]
    assert payload["input_adapters"][2]["aliases"] == ["PIKARaw"]
    assert payload["input_adapters"][3]["aliases"] == ["W1Teleop"]
    hdf5_source = payload["input_adapters"][0]["capabilities"]["source"]
    pika_source = payload["input_adapters"][2]["capabilities"]["source"]
    w1_source = payload["input_adapters"][3]["capabilities"]["source"]
    assert hdf5_source["directory_upload"] == "top_level_matching"
    assert hdf5_source["file_extensions"] == [".hdf5", ".h5"]
    assert pika_source["directory_upload"] == "recursive"
    assert w1_source["directory_upload"] == "recursive"
    assert w1_source["supports_file_upload"] is False
    assert payload["output_exporters"][0]["name"] == "HDF5EpisodeExporter"
    assert payload["output_exporters"][0]["aliases"] == ["HDF5"]
    assert payload["reachability_backends"][0]["name"] == "MockReachabilityBackend"
    assert payload["quality_backends"][0]["name"] == "DTWTrajectoryQualityBackend"
    assert payload["quality_backends"][1]["name"] == "SmoothnessTrajectoryQualityBackend"


def test_quality_backends_endpoint_uses_discovered_components() -> None:
    """Verify quality router exposes automatically discovered quality backends."""

    client = TestClient(create_app())
    response = client.get("/api/quality/backends")

    assert response.status_code == 200
    assert [item["name"] for item in response.json()] == [
        "DTWTrajectoryQualityBackend",
        "SmoothnessTrajectoryQualityBackend",
    ]
