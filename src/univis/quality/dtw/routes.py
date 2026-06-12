"""FastAPI routes for DTW quality tools."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from univis.quality.service import QualityService

DEFAULT_BACKEND = "DTWTrajectoryQualityBackend"


class DTWCompareRequest(BaseModel):
    """Request for current-vs-reference DTW comparison."""

    current_episode_id: str
    reference_episode_id: str
    backend_name: str = DEFAULT_BACKEND


class DTWSelectedStatsRequest(BaseModel):
    """Request for selected episode DTW statistics."""

    reference_episode_id: str
    episode_ids: list[str]
    backend_name: str = DEFAULT_BACKEND


def build_dtw_router(service: QualityService) -> APIRouter:
    """Build DTW quality API routes.

    Inputs:
        service: Shared quality service bound to the active episode session.
    Output:
        Router mounted under `/api/quality/dtw`.
    """

    router = APIRouter(prefix="/dtw")

    @router.post("/compare")
    def compare_dtw(request: DTWCompareRequest) -> dict:
        """Compare one current episode against a reference episode."""

        try:
            return service.compare(
                request.current_episode_id,
                request.reference_episode_id,
                request.backend_name,
            ).model_dump()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="episode not found") from exc
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/selected-stats")
    def selected_stats(request: DTWSelectedStatsRequest) -> dict:
        """Aggregate selected episode DTW stats against one reference."""

        try:
            return service.selected_stats(
                request.reference_episode_id,
                request.episode_ids,
                request.backend_name,
            ).model_dump()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="episode not found") from exc
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return router
