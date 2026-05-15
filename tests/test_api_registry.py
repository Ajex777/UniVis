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
        "PikaRawEpisodeAdapter",
    ]
    assert payload["output_exporters"][0]["name"] == "HDF5EpisodeExporter"
    assert payload["reachability_backends"][0]["name"] == "MockReachabilityBackend"
