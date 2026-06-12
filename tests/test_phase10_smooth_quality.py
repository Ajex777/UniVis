"""Tests for smooth trajectory quality."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from univis.base_io.adapters import EpisodeSource, RawEpisodeAdapter
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
from univis.quality import DTWTrajectoryQualityBackend, SmoothnessTrajectoryQualityBackend
from univis.quality.models import SmoothnessConfig, SmoothnessScopeConfig
from univis.quality.settings import QualityConfig


class SmoothQualityTestAdapter(RawEpisodeAdapter):
    """Small in-memory adapter used by smoothness API tests."""

    @classmethod
    def info(cls) -> ComponentInfo:
        return ComponentInfo(name="SmoothQualityTestAdapter", label="Smooth Quality Test")

    def list_metadata(self, source: EpisodeSource | None = None):
        return [self.load_episode(episode_id).metadata for episode_id in self._ids()]

    def load_episode(self, episode_id: str, source: EpisodeSource | None = None):
        values = {
            "linear": [0.0, 0.1, 0.2, 0.3, 0.4],
            "jump": [0.0, 0.1, 1.5, 0.3, 0.4],
        }[episode_id]
        return _episode(episode_id, values)

    def _ids(self) -> list[str]:
        return ["linear", "jump"]


def _episode(episode_id: str, xs: list[float], dt: float = 0.1) -> PolicyEpisode:
    """Build one tiny PolicyEpisode for smoothness tests."""

    frames = []
    for index, x in enumerate(xs):
        arm = ArmFrame(
            xyz=[x, 0.0, 0.0],
            rot6d=[1.0, 0.0, 0.0, 0.0, 1.0, 0.0],
            gripper=0.5,
        )
        frames.append(
            PolicyFrame(index=index, timestamp=float(index) * dt, left=arm, right=arm)
        )
    metadata = PolicyEpisodeMetadata(
        episode_id=episode_id,
        title=episode_id,
        num_frames=len(frames),
        fps=1.0 / dt,
        cameras=[CameraStream(key="cam", label="Cam", width=8, height=8)],
        annotation=Annotation(),
    )
    return PolicyEpisode(metadata=metadata, frames=frames)


def _strict_config() -> SmoothnessConfig:
    scope = SmoothnessScopeConfig(
        enabled=True,
        source="left.xyz",
        acceleration_cost_threshold=1.0,
        jerk_cost_threshold=1.0,
    )
    return SmoothnessConfig(
        use_episode_timestamps=True,
        fps_fallback=10.0,
        scopes={"left_eef_position": scope},
    )


def test_linear_constant_velocity_is_smooth() -> None:
    """A constant-velocity line should have zero acceleration and jerk cost."""

    report = SmoothnessTrajectoryQualityBackend(_strict_config()).assess(
        _episode("linear", [0.0, 0.1, 0.2, 0.3, 0.4])
    )
    summary = report.scopes["left_eef_position"]
    assert report.passed
    assert summary.acceleration_cost < 1e-10
    assert summary.jerk_cost < 1e-10


def test_jump_trajectory_fails_smoothness_thresholds() -> None:
    """A position jump should produce high acceleration/jerk costs."""

    report = SmoothnessTrajectoryQualityBackend(_strict_config()).assess(
        _episode("jump", [0.0, 0.1, 1.5, 0.3, 0.4])
    )
    summary = report.scopes["left_eef_position"]
    assert not report.passed
    assert summary.acceleration_cost > 1.0
    assert summary.jerk_cost > 1.0
    assert summary.warnings


def test_default_smoothness_config_loads() -> None:
    """Verify packaged smoothness defaults are exposed through QualityConfig."""

    config = QualityConfig.load().smoothness
    assert config.use_episode_timestamps
    assert config.scopes["left_eef_position"].enabled
    assert not config.scopes["left_eef_rotation6d"].enabled


def test_quality_smooth_episode_api() -> None:
    """Verify smoothness API response shape."""

    session = EpisodeSession([SmoothQualityTestAdapter()], "SmoothQualityTestAdapter")
    app = FastAPI()
    app.include_router(
        QualityRouter(
            session,
            [DTWTrajectoryQualityBackend(), SmoothnessTrajectoryQualityBackend(_strict_config())],
        ).router
    )
    response = TestClient(app).post(
        "/api/quality/smooth/episode",
        json={"episode_id": "jump"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["episode_id"] == "jump"
    assert payload["passed"] is False
    assert "left_eef_position" in payload["scopes"]
