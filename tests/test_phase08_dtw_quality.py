"""Tests for Phase 08 DTW trajectory quality."""

import numpy as np

from univis.domain.policy_episode import (
    Annotation,
    ArmFrame,
    CameraStream,
    PolicyEpisode,
    PolicyEpisodeMetadata,
    PolicyFrame,
)
from univis.quality.dtw import DTWTrajectoryQualityBackend, PoseDTWComparator
from univis.quality.models import PoseDTWConfig
from univis.quality.settings import QualityConfig


def _episode(episode_id: str, xs: list[float], right_offset: float = 0.0) -> PolicyEpisode:
    """Create a tiny dual-arm episode for DTW tests."""

    frames = []
    for index, x in enumerate(xs):
        left = ArmFrame(
            xyz=[x, 0.0, 0.0],
            rot6d=[1.0, 0.0, 0.0, 0.0, 1.0, 0.0],
            gripper=0.5,
        )
        right = ArmFrame(
            xyz=[x, right_offset, 0.0],
            rot6d=[1.0, 0.0, 0.0, 0.0, 1.0, 0.0],
            gripper=0.5,
        )
        frames.append(PolicyFrame(index=index, timestamp=float(index), left=left, right=right))
    metadata = PolicyEpisodeMetadata(
        episode_id=episode_id,
        title=episode_id,
        num_frames=len(frames),
        fps=10.0,
        cameras=[CameraStream(key="cam", label="Cam", width=8, height=8)],
        annotation=Annotation(),
    )
    return PolicyEpisode(metadata=metadata, frames=frames)


def test_identity_trajectory_has_zero_cost() -> None:
    """Identical trajectories should report near-zero DTW error."""

    traj = np.array([
        [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0],
        [0.1, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0],
    ])
    result = PoseDTWComparator(PoseDTWConfig()).compare_arm(traj, traj)
    assert result.summary.dtw_cost_normalized == 0.0
    assert result.summary.mean_rotation_error_deg == 0.0


def test_different_length_same_shape_aligns_with_low_error() -> None:
    """DTW should align same-shape trajectories with different sampling."""

    current = _episode("current", [0.0, 0.05, 0.1, 0.15, 0.2])
    reference = _episode("ref", [0.0, 0.1, 0.2])
    comparison = DTWTrajectoryQualityBackend().compare(current, reference)
    assert comparison.left.summary.mean_position_error < 0.04
    assert comparison.left.summary.path_length >= 5


def test_left_and_right_metrics_remain_independent() -> None:
    """Right arm offset should not pollute left arm metrics."""

    current = _episode("current", [0.0, 0.1, 0.2], right_offset=0.2)
    reference = _episode("ref", [0.0, 0.1, 0.2], right_offset=0.0)
    comparison = DTWTrajectoryQualityBackend().compare(current, reference)
    assert comparison.left.summary.dtw_cost_normalized == 0.0
    assert comparison.right.summary.mean_position_error > 0.1


def test_selected_stats() -> None:
    """Backend should aggregate selected episodes against one reference."""

    ref = _episode("ref", [0.0, 0.1, 0.2])
    close = _episode("close", [0.0, 0.11, 0.2])
    far = _episode("far", [0.0, 0.4, 0.8])
    backend = DTWTrajectoryQualityBackend()
    stats = backend.selected_stats([close, far], ref)
    assert stats.reference_episode_id == "ref"
    assert stats.abnormal_episodes[0].episode_id == "far"


def test_visual_links_are_decimated() -> None:
    """Frontend link payload should be capped by config."""

    current = _episode("current", [float(i) for i in range(20)])
    reference = _episode("ref", [float(i) for i in range(20)])
    backend = DTWTrajectoryQualityBackend(PoseDTWConfig(max_visual_links=5))
    comparison = backend.compare(current, reference)
    assert len(comparison.left.visual_links) == 5


def test_default_dtw_config_loads_from_structured_yaml() -> None:
    """Verify packaged structured YAML drives DTW defaults."""

    config = QualityConfig.load().dtw
    assert config.pos_scale == 0.01
    assert config.rot_scale_deg == 5.0
    assert config.window_ratio == 0.2
    assert config.max_visual_links == 120
    assert config.percentile == 95.0
