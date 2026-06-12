"""FastAPI route aggregation for trajectory quality tools."""

from __future__ import annotations

from fastapi import APIRouter

from univis.core.episode_session import EpisodeSession
from univis.quality.base import QualityBackend, QualityRouteBuilder
from univis.quality.registry import load_quality_components
from univis.quality.service import QualityService


class QualityRouter:
    """Route container for pluggable trajectory quality APIs."""

    def __init__(
        self,
        session: EpisodeSession,
        backends: list[QualityBackend],
        route_builders: list[QualityRouteBuilder] | None = None,
    ) -> None:
        """Initialize router with episode session, backends, and feature routes.

        Inputs:
            session: Active episode session.
            backends: Registered quality backend instances.
            route_builders: Feature-owned router factories.
        Output:
            Router mounted at `/api/quality`.
        """

        self.service = QualityService(session, backends)
        self.route_builders = route_builders
        if self.route_builders is None:
            self.route_builders = load_quality_components().route_builders
        self.router = APIRouter(prefix="/api/quality")
        self._register()

    def _register(self) -> None:
        """Register shared and feature-owned quality API routes."""

        self.router.add_api_route("/backends", self.list_backends, methods=["GET"])
        for build_router in self.route_builders:
            self.router.include_router(build_router(self.service))

    def list_backends(self) -> list[dict]:
        """Return quality backend metadata."""

        return [backend.info().model_dump() for backend in self.service.backends.values()]
