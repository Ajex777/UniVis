"""Template FastAPI routes for a UniVis quality feature."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from univis.quality.service import QualityService

DEFAULT_BACKEND = "TemplateQualityBackend"


class TemplateCompareRequest(BaseModel):
    """Request for pairwise current/reference comparison."""

    current_episode_id: str
    reference_episode_id: str
    backend_name: str = DEFAULT_BACKEND


class TemplateAssessRequest(BaseModel):
    """Request for single-episode assessment."""

    episode_id: str
    backend_name: str = DEFAULT_BACKEND


def build_template_quality_router(service: QualityService) -> APIRouter:
    """Build template quality API routes.

    Inputs:
        service: Shared quality service bound to the active episode session.
    Output:
        Router mounted under `/api/quality/template` if registered.

    Design note:
        Route functions should only parse requests, call `QualityService`, and
        translate exceptions. Algorithm logic belongs in the backend.
    """

    router = APIRouter(prefix="/template")

    @router.post("/compare")
    def compare(request: TemplateCompareRequest) -> dict:
        """Compare current and reference episodes with the selected backend."""

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

    @router.post("/episode")
    def assess_episode(request: TemplateAssessRequest) -> dict:
        """Assess one episode without a reference episode."""

        try:
            return service.assess_episode(request.episode_id, request.backend_name).model_dump()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="episode not found") from exc
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return router
