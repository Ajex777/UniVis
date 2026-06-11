"""FastAPI routes for trajectory quality tools."""

from __future__ import annotations

from pydantic import BaseModel
from fastapi import APIRouter, HTTPException

from univis.core.episode_session import EpisodeSession
from univis.core.quality_service import QualityService
from univis.quality.base import TrajectoryQualityBackend


class DTWCompareRequest(BaseModel):
    """Request for current-vs-reference DTW comparison."""

    current_episode_id: str
    reference_episode_id: str
    backend_name: str = "DTWTrajectoryQualityBackend"


class DTWSelectedStatsRequest(BaseModel):
    """Request for selected episode DTW statistics."""

    reference_episode_id: str
    episode_ids: list[str]
    backend_name: str = "DTWTrajectoryQualityBackend"


class SmoothEpisodeRequest(BaseModel):
    """Request for one episode smoothness assessment."""

    episode_id: str
    backend_name: str = "SmoothnessTrajectoryQualityBackend"


class QualityRouter:
    """Route container for trajectory quality APIs."""

    def __init__(
        self,
        session: EpisodeSession,
        backends: list[TrajectoryQualityBackend],
    ) -> None:
        """Initialize router with episode session and quality backends."""

        self.service = QualityService(session, backends)
        self.router = APIRouter(prefix="/api/quality")
        self._register()

    def _register(self) -> None:
        """Register quality API routes."""

        self.router.add_api_route("/backends", self.list_backends, methods=["GET"])
        self.router.add_api_route("/dtw/compare", self.compare_dtw, methods=["POST"])
        self.router.add_api_route("/dtw/selected-stats", self.selected_stats, methods=["POST"])
        self.router.add_api_route("/smooth/episode", self.smooth_episode, methods=["POST"])

    def list_backends(self) -> list[dict]:
        """Return quality backend metadata."""

        return [backend.info().model_dump() for backend in self.service.backends.values()]

    def compare_dtw(self, request: DTWCompareRequest) -> dict:
        """Compare one current episode against a reference episode."""

        try:
            return self.service.compare_dtw(
                request.current_episode_id,
                request.reference_episode_id,
                request.backend_name,
            ).model_dump()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="episode not found") from exc
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    def selected_stats(self, request: DTWSelectedStatsRequest) -> dict:
        """Aggregate selected episode DTW stats against one reference."""

        try:
            return self.service.selected_stats(
                request.reference_episode_id,
                request.episode_ids,
                request.backend_name,
            ).model_dump()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="episode not found") from exc
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    def smooth_episode(self, request: SmoothEpisodeRequest) -> dict:
        """Assess one episode's trajectory smoothness."""

        try:
            return self.service.smooth_episode(
                request.episode_id,
                request.backend_name,
            ).model_dump()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="episode not found") from exc
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
