"""DTW quality feature package."""

from univis.quality.base import QualityComponentBundle
from univis.quality.dtw.backend import DTWTrajectoryQualityBackend, PoseDTWComparator
from univis.quality.dtw.models import (
    ArmDTWAlignment,
    ArmDTWSummary,
    EpisodeDTWComparison,
    EpisodeDTWScore,
    PoseDTWConfig,
    SelectedEpisodeDTWStats,
)
from univis.quality.dtw.routes import build_dtw_router

QUALITY_ORDER = 10


def quality_components() -> QualityComponentBundle:
    """Return DTW backend and API route contributions."""

    return QualityComponentBundle(
        backends=[DTWTrajectoryQualityBackend()],
        route_builders=[build_dtw_router],
    )


__all__ = [
    "ArmDTWAlignment",
    "ArmDTWSummary",
    "DTWTrajectoryQualityBackend",
    "EpisodeDTWComparison",
    "EpisodeDTWScore",
    "PoseDTWComparator",
    "PoseDTWConfig",
    "QUALITY_ORDER",
    "SelectedEpisodeDTWStats",
    "quality_components",
]
