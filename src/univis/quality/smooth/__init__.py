"""Smoothness quality feature package."""

from univis.quality.base import QualityComponentBundle
from univis.quality.smooth.backend import SmoothnessTrajectoryQualityBackend
from univis.quality.smooth.models import (
    ArmSmoothnessSummary,
    EpisodeSmoothnessReport,
    SmoothnessConfig,
    SmoothnessScopeConfig,
)
from univis.quality.smooth.routes import build_smooth_router

QUALITY_ORDER = 20


def quality_components() -> QualityComponentBundle:
    """Return smoothness backend and API route contributions."""

    return QualityComponentBundle(
        backends=[SmoothnessTrajectoryQualityBackend()],
        route_builders=[build_smooth_router],
    )


__all__ = [
    "ArmSmoothnessSummary",
    "EpisodeSmoothnessReport",
    "QUALITY_ORDER",
    "SmoothnessConfig",
    "SmoothnessScopeConfig",
    "SmoothnessTrajectoryQualityBackend",
    "quality_components",
]
