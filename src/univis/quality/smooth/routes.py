"""FastAPI routes for smoothness quality tools."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from univis.quality.service import QualityService

DEFAULT_BACKEND = "SmoothnessTrajectoryQualityBackend"


class SmoothEpisodeRequest(BaseModel):
    """Request for one episode smoothness assessment."""

    episode_id: str
    backend_name: str = DEFAULT_BACKEND


def build_smooth_router(service: QualityService) -> APIRouter:
    """Build smoothness quality API routes.

    Inputs:
        service: Shared quality service bound to the active episode session.
    Output:
        Router mounted under `/api/quality/smooth`.
    """

    router = APIRouter(prefix="/smooth")

    @router.post("/episode")
    def smooth_episode(request: SmoothEpisodeRequest) -> dict:
        """Assess one episode's trajectory smoothness."""

        try:
            return service.assess_episode(request.episode_id, request.backend_name).model_dump()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="episode not found") from exc
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return router
