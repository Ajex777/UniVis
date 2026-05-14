"""Tests for Phase 01 core abstraction contracts."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from univis.adapters.base import EpisodeSource, RawEpisodeAdapter
from univis.core.components import ComponentRegistry
from univis.domain.policy_episode import (
    Annotation,
    ArmFrame,
    CameraStream,
    PolicyEpisode,
    PolicyEpisodeMetadata,
    PolicyFrame,
    ReachabilityOverlay,
)
from univis.exporters.mock import MockEpisodeExporter
from univis.reachability.mock import MockReachabilityBackend


class InlineEpisodeAdapter(RawEpisodeAdapter):
    """Small concrete adapter used only for abstraction tests."""

    @classmethod
    def info(cls):
        from univis.core.components import ComponentInfo

        return ComponentInfo(
            name="InlineEpisodeAdapter",
            label="Inline Episode",
            description="Test-only synchronized episode adapter.",
        )

    def list_metadata(self, source: EpisodeSource | None = None):
        return [_metadata()]

    def load_episode(self, episode_id: str, source: EpisodeSource | None = None):
        return PolicyEpisode(metadata=_metadata(), frames=[_frame(0), _frame(1)])


def _frame(index: int) -> PolicyFrame:
    """Create one valid dual-arm frame for shape tests.

    Inputs:
        index: Contiguous frame index.
    Output:
        Minimal valid `PolicyFrame`.
    """

    arm = ArmFrame(
        xyz=[0.1, 0.2, 0.3],
        rot6d=[1.0, 0.0, 0.0, 0.0, 1.0, 0.0],
        gripper=0.5,
    )
    return PolicyFrame(index=index, timestamp=float(index), left=arm, right=arm)


def _metadata(num_frames: int = 2) -> PolicyEpisodeMetadata:
    """Create valid metadata for shape tests.

    Inputs:
        num_frames: Expected number of synchronized frames.
    Output:
        Minimal valid metadata with one camera and matching reachability.
    """

    return PolicyEpisodeMetadata(
        episode_id="episode-test",
        title="Episode Test",
        num_frames=num_frames,
        fps=10.0,
        cameras=[CameraStream(key="head_rgb", label="Head RGB", width=64, height=48)],
        annotation=Annotation(language_prompt="test"),
        reachability=ReachabilityOverlay(
            reachable=[True] * num_frames,
            reasons=[""] * num_frames,
        ),
    )


def test_policy_episode_validates_shape() -> None:
    """Verify frame count and indices must match metadata.

    Inputs:
        None.
    Output:
        Assertions covering valid and invalid `PolicyEpisode` shapes.
    """

    episode = PolicyEpisode(metadata=_metadata(), frames=[_frame(0), _frame(1)])
    assert episode.metadata.num_frames == 2

    with pytest.raises(ValidationError, match="frames length"):
        PolicyEpisode(metadata=_metadata(num_frames=3), frames=[_frame(0), _frame(1)])

    with pytest.raises(ValidationError, match="contiguous"):
        PolicyEpisode(metadata=_metadata(), frames=[_frame(0), _frame(2)])


def test_metadata_validates_camera_and_reachability_shape() -> None:
    """Verify metadata catches camera key and overlay mismatches.

    Inputs:
        None.
    Output:
        Assertions that invalid metadata raises validation errors.
    """

    with pytest.raises(ValidationError, match="camera keys"):
        PolicyEpisodeMetadata(
            episode_id="dup",
            title="Dup",
            num_frames=1,
            fps=10.0,
            cameras=[
                CameraStream(key="head", label="A", width=64, height=48),
                CameraStream(key="head", label="B", width=64, height=48),
            ],
            annotation=Annotation(),
        )

    with pytest.raises(ValidationError, match="reachability flags"):
        PolicyEpisodeMetadata(
            episode_id="bad-overlay",
            title="Bad Overlay",
            num_frames=2,
            fps=10.0,
            cameras=[CameraStream(key="head", label="Head", width=64, height=48)],
            annotation=Annotation(),
            reachability=ReachabilityOverlay(reachable=[True], reasons=["", ""]),
        )


def test_mock_adapter_exporter_reachability_flow(tmp_path: Path) -> None:
    """Verify RawEpisodeAdapter -> PolicyEpisode -> EpisodeExporter flow.

    Inputs:
        tmp_path: Temporary output root provided by pytest.
    Output:
        Assertions that mock implementations interoperate through interfaces.
    """

    adapter = InlineEpisodeAdapter()
    metadata = adapter.list_metadata(EpisodeSource())
    episode = adapter.load_episode(metadata[0].episode_id)

    report = MockReachabilityBackend().evaluate(episode)
    result = MockEpisodeExporter().export(episode, tmp_path)

    assert report.episode_id == episode.metadata.episode_id
    assert report.summary["num_frames"] == episode.metadata.num_frames
    assert result.success is True
    assert result.output_path.endswith(".mock.json")


def test_component_registry_payload() -> None:
    """Verify registry serializes registered component info.

    Inputs:
        None.
    Output:
        Assertions that UI/API dropdown payloads come from component metadata.
    """

    registry = ComponentRegistry(
        input_adapters=[InlineEpisodeAdapter()],
        output_exporters=[MockEpisodeExporter()],
        reachability_backends=[MockReachabilityBackend()],
    )
    payload = registry.api_payload()
    assert payload["input_adapters"][0]["name"] == "InlineEpisodeAdapter"
    assert payload["output_exporters"][0]["name"] == "MockEpisodeExporter"
    assert payload["reachability_backends"][0]["name"] == "MockReachabilityBackend"
