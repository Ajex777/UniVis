"""API tests for Phase 08 trajectory quality routes."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from univis.adapters.base import EpisodeSource, RawEpisodeAdapter
from univis.api.quality import QualityRouter
from univis.core.components import ComponentInfo
from univis.core.episode_session import EpisodeSession
from univis.domain.policy_episode import (
    Annotation,
    ArmFrame,
    CameraStream,
    PolicyEpisode,
    PolicyEpisodeMetadata,
    PolicyFrame,
)
from univis.quality import DTWTrajectoryQualityBackend


class QualityTestAdapter(RawEpisodeAdapter):
    """Small in-memory adapter used by quality API tests."""

    @classmethod
    def info(cls) -> ComponentInfo:
        return ComponentInfo(name="QualityTestAdapter", label="Quality Test")

    def list_metadata(self, source: EpisodeSource | None = None):
        return [self.load_episode(episode_id).metadata for episode_id in self._ids()]

    def load_episode(self, episode_id: str, source: EpisodeSource | None = None):
        values = {
            "ref": [0.0, 0.1, 0.2],
            "close": [0.0, 0.11, 0.2],
            "far": [0.0, 0.4, 0.8],
        }[episode_id]
        return _episode(episode_id, values)

    def _ids(self) -> list[str]:
        return ["ref", "close", "far"]


def _episode(episode_id: str, xs: list[float]) -> PolicyEpisode:
    """Build one small PolicyEpisode for API route tests."""

    frames = []
    for index, x in enumerate(xs):
        arm = ArmFrame(
            xyz=[x, 0.0, 0.0],
            rot6d=[1.0, 0.0, 0.0, 0.0, 1.0, 0.0],
            gripper=0.5,
        )
        frames.append(PolicyFrame(index=index, timestamp=float(index), left=arm, right=arm))
    metadata = PolicyEpisodeMetadata(
        episode_id=episode_id,
        title=episode_id,
        num_frames=len(frames),
        fps=10.0,
        cameras=[CameraStream(key="cam", label="Cam", width=8, height=8)],
        annotation=Annotation(),
    )
    return PolicyEpisode(metadata=metadata, frames=frames)


def _client() -> TestClient:
    """Create a FastAPI client with quality routes only."""

    session = EpisodeSession([QualityTestAdapter()], "QualityTestAdapter")
    app = FastAPI()
    app.include_router(QualityRouter(session, [DTWTrajectoryQualityBackend()]).router)
    return TestClient(app)


def test_quality_compare_api() -> None:
    """Verify current/reference DTW API response shape."""

    response = _client().post(
        "/api/quality/dtw/compare",
        json={"current_episode_id": "close", "reference_episode_id": "ref"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["current_episode_id"] == "close"
    assert payload["reference_episode_id"] == "ref"
    assert "visual_links" in payload["left"]


def test_quality_selected_stats_api() -> None:
    """Verify selected stats endpoint."""

    client = _client()
    stats = client.post(
        "/api/quality/dtw/selected-stats",
        json={"reference_episode_id": "ref", "episode_ids": ["close", "far"]},
    )
    assert stats.status_code == 200
    payload = stats.json()
    assert payload["reference_episode_id"] == "ref"
    assert payload["abnormal_episodes"][0]["episode_id"] == "far"
