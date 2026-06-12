"""Static DTW comparison visualization for CLI reports."""

from __future__ import annotations

from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402

from univis.domain.policy_episode import PolicyEpisode
from univis.quality.dtw.extractors import DualArmEEFExtractor
from univis.quality.dtw.models import EpisodeDTWComparison


class DTWComparisonPlotter:
    """Render current/reference DTW trajectory comparison images."""

    COLORS = {
        "left_current": "#14785f",
        "right_current": "#b87300",
        "left_reference": "#54b9a4",
        "right_reference": "#d6a33c",
        "left_links": "#73958d",
        "right_links": "#a98b53",
    }

    def __init__(self) -> None:
        """Initialize the plotter with the shared EEF trajectory extractor."""

        self.extractor = DualArmEEFExtractor()

    def render_png(
        self,
        current: PolicyEpisode,
        reference: PolicyEpisode,
        comparison: EpisodeDTWComparison,
        output_path: Path,
    ) -> Path:
        """Render one static PNG similar to the GUI DTW overlay."""

        current_pose = self.extractor.extract(current)
        reference_pose = self.extractor.extract(reference)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig = plt.figure(figsize=(11, 9), dpi=150)
        axis = fig.add_subplot(111, projection="3d")
        self._plot_arm(axis, current_pose.left[:, :3], "left current", self.COLORS["left_current"], 3.0)
        self._plot_arm(axis, current_pose.right[:, :3], "right current", self.COLORS["right_current"], 3.0)
        self._plot_arm(axis, reference_pose.left[:, :3], "left reference", self.COLORS["left_reference"], 2.0)
        self._plot_arm(axis, reference_pose.right[:, :3], "right reference", self.COLORS["right_reference"], 2.0)
        self._plot_links(
            axis,
            current_pose.left[:, :3],
            reference_pose.left[:, :3],
            comparison.left.visual_links,
            self.COLORS["left_links"],
        )
        self._plot_links(
            axis,
            current_pose.right[:, :3],
            reference_pose.right[:, :3],
            comparison.right.visual_links,
            self.COLORS["right_links"],
        )
        self._style_axis(axis, [
            current_pose.left[:, :3],
            current_pose.right[:, :3],
            reference_pose.left[:, :3],
            reference_pose.right[:, :3],
        ])
        fig.tight_layout()
        fig.savefig(output_path, bbox_inches="tight")
        plt.close(fig)
        return output_path

    def _plot_arm(self, axis, points: np.ndarray, label: str, color: str, width: float) -> None:
        """Plot one 3D EEF trajectory line."""

        axis.plot(points[:, 0], points[:, 1], points[:, 2], color=color, linewidth=width, label=label)

    def _plot_links(
        self,
        axis,
        current: np.ndarray,
        reference: np.ndarray,
        links: list[tuple[int, int]],
        color: str,
    ) -> None:
        """Plot decimated DTW alignment links as faint 3D segments."""

        for current_idx, reference_idx in links:
            if current_idx >= len(current) or reference_idx >= len(reference):
                continue
            start = current[current_idx]
            end = reference[reference_idx]
            axis.plot(
                [start[0], end[0]],
                [start[1], end[1]],
                [start[2], end[2]],
                color=color,
                linewidth=0.8,
                alpha=0.32,
            )

    def _style_axis(self, axis, point_sets: list[np.ndarray]) -> None:
        """Apply labels, legend, view angle, and equal-ish 3D bounds."""

        axis.set_xlabel("x")
        axis.set_ylabel("y")
        axis.set_zlabel("z")
        axis.view_init(elev=22, azim=-135)
        all_points = np.concatenate(point_sets, axis=0)
        center = all_points.mean(axis=0)
        radius = max(float(np.ptp(all_points[:, dim])) for dim in range(3)) / 2.0
        radius = max(radius, 1e-3)
        axis.set_xlim(center[0] - radius, center[0] + radius)
        axis.set_ylim(center[1] - radius, center[1] + radius)
        axis.set_zlim(center[2] - radius, center[2] + radius)
        axis.grid(True, alpha=0.25)
        axis.legend(loc="upper right")
