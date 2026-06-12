"""DTW trajectory quality backend."""

from __future__ import annotations

import math

import numpy as np

from univis.core.components import ComponentInfo
from univis.domain.policy_episode import PolicyEpisode
from univis.quality.base import PairwiseQualityBackend, ReferenceBatchQualityBackend
from univis.quality.dtw.extractors import DualArmEEFExtractor
from univis.quality.dtw.math import (
    compute_dtw,
    decimate_path,
    degrees,
    percentile,
    rot6d_to_matrix,
    rotation_distance_rad,
    warp_distortion,
)
from univis.quality.dtw.models import (
    ArmDTWAlignment,
    ArmDTWSummary,
    EpisodeDTWComparison,
    EpisodeDTWScore,
    PoseDTWConfig,
    SelectedEpisodeDTWStats,
)
from univis.quality.dtw.settings import DTWQualityConfig


class PoseDTWComparator:
    """Compare two single-arm xyz + rot6d trajectories with DTW."""

    def __init__(self, config: PoseDTWConfig | None = None) -> None:
        self.config = config or PoseDTWConfig()

    def compare_arm(self, current: np.ndarray, reference: np.ndarray) -> ArmDTWAlignment:
        """Return DTW alignment and metrics for one arm."""

        current = np.asarray(current, dtype=np.float64)
        reference = np.asarray(reference, dtype=np.float64)
        if current.ndim != 2 or reference.ndim != 2:
            raise ValueError("trajectory arrays must be 2D")
        if current.shape[1] != 9 or reference.shape[1] != 9:
            raise ValueError("trajectory arrays must have shape (T, 9)")
        pos_errors, rot_errors = self._pairwise_errors(current, reference)
        pose_cost = np.sqrt(
            (pos_errors / self.config.pos_scale) ** 2
            + (rot_errors / math.radians(self.config.rot_scale_deg)) ** 2
        )
        total_cost, path = compute_dtw(pose_cost, self._window(current, reference))
        aligned_pos = [float(pos_errors[i, j]) for i, j in path]
        aligned_rot = [float(rot_errors[i, j]) for i, j in path]
        rot_deg = degrees(aligned_rot)
        final_rot = float(rotation_distance_rad(
            rot6d_to_matrix(current[-1, 3:9]),
            rot6d_to_matrix(reference[-1, 3:9]),
        ))
        summary = ArmDTWSummary(
            dtw_cost=total_cost,
            dtw_cost_normalized=total_cost / len(path),
            mean_position_error=float(np.mean(aligned_pos)),
            p95_position_error=percentile(aligned_pos, self.config.percentile),
            max_position_error=float(np.max(aligned_pos)),
            final_position_error=float(np.linalg.norm(current[-1, :3] - reference[-1, :3])),
            mean_rotation_error_deg=float(np.mean(rot_deg)),
            p95_rotation_error_deg=percentile(rot_deg, self.config.percentile),
            max_rotation_error_deg=float(np.max(rot_deg)),
            final_rotation_error_deg=math.degrees(final_rot),
            warp_distortion=warp_distortion(path, len(current), len(reference)),
            path_length=len(path),
            length_current=len(current),
            length_reference=len(reference),
            length_ratio=len(current) / max(1, len(reference)),
        )
        return ArmDTWAlignment(
            summary=summary,
            warping_path=path,
            visual_links=decimate_path(path, self.config.max_visual_links),
        )

    def _pairwise_errors(self, current: np.ndarray, reference: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Compute pairwise position and rotation errors."""

        pos_errors = np.linalg.norm(current[:, None, :3] - reference[None, :, :3], axis=-1)
        cur_rot = rot6d_to_matrix(current[:, 3:9])
        ref_rot = rot6d_to_matrix(reference[:, 3:9])
        rot_errors = rotation_distance_rad(cur_rot[:, None, :, :], ref_rot[None, :, :, :])
        return pos_errors, rot_errors

    def _window(self, current: np.ndarray, reference: np.ndarray) -> int | None:
        """Return Sakoe-Chiba window size from current config."""

        if self.config.window_ratio is None:
            return None
        return int(max(len(current), len(reference)) * self.config.window_ratio)


class DTWTrajectoryQualityBackend(PairwiseQualityBackend, ReferenceBatchQualityBackend):
    """PolicyEpisode quality backend using dual-arm pose DTW."""

    def __init__(self, config: PoseDTWConfig | None = None) -> None:
        self.config = config or DTWQualityConfig.load()
        self.extractor = DualArmEEFExtractor()
        self.comparator = PoseDTWComparator(self.config)

    @classmethod
    def info(cls) -> ComponentInfo:
        return ComponentInfo(
            name="DTWTrajectoryQualityBackend",
            label="Dynamic Time Warping",
            description="Compare current and reference EEF trajectories with DTW.",
        )

    def compare(self, current: PolicyEpisode, reference: PolicyEpisode) -> EpisodeDTWComparison:
        """Compare current episode against reference for left and right arms."""

        cur = self.extractor.extract(current)
        ref = self.extractor.extract(reference)
        return EpisodeDTWComparison(
            current_episode_id=current.metadata.episode_id,
            reference_episode_id=reference.metadata.episode_id,
            left=self.comparator.compare_arm(cur.left, ref.left),
            right=self.comparator.compare_arm(cur.right, ref.right),
        )

    def selected_stats(
        self,
        episodes: list[PolicyEpisode],
        reference: PolicyEpisode,
    ) -> SelectedEpisodeDTWStats:
        """Aggregate selected episode metrics against one reference."""

        comparisons = [self.compare(episode, reference) for episode in episodes]
        left_values = [item.left.summary for item in comparisons]
        right_values = [item.right.summary for item in comparisons]
        scores = [
            EpisodeDTWScore(
                episode_id=item.current_episode_id,
                left_dtw_cost_normalized=item.left.summary.dtw_cost_normalized,
                right_dtw_cost_normalized=item.right.summary.dtw_cost_normalized,
                left_p95_position_error=item.left.summary.p95_position_error,
                right_p95_position_error=item.right.summary.p95_position_error,
            )
            for item in comparisons
        ]
        scores.sort(
            key=lambda item: item.left_dtw_cost_normalized + item.right_dtw_cost_normalized,
            reverse=True,
        )
        return SelectedEpisodeDTWStats(
            reference_episode_id=reference.metadata.episode_id,
            selected_episode_ids=[episode.metadata.episode_id for episode in episodes],
            left_summary=_aggregate(left_values),
            right_summary=_aggregate(right_values),
            abnormal_episodes=scores[:10],
        )


def _aggregate(summaries: list[ArmDTWSummary]) -> dict[str, float]:
    """Aggregate a list of arm summaries for selected stats."""

    if not summaries:
        return {}
    fields = (
        "dtw_cost_normalized",
        "mean_position_error",
        "p95_position_error",
        "max_position_error",
        "mean_rotation_error_deg",
        "p95_rotation_error_deg",
        "max_rotation_error_deg",
        "warp_distortion",
    )
    result: dict[str, float] = {}
    for field in fields:
        values = np.asarray([getattr(summary, field) for summary in summaries], dtype=np.float64)
        result[f"{field}_mean"] = float(np.mean(values))
        result[f"{field}_p95"] = float(np.percentile(values, 95.0))
        result[f"{field}_max"] = float(np.max(values))
    return result
