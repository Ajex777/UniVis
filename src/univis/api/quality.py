"""FastAPI routes for trajectory quality tools."""

from __future__ import annotations

from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException

from univis.core.episode_session import EpisodeSession
from univis.quality.base import TrajectoryQualityBackend


class DTWCompareRequest(BaseModel):
    """Request for current-vs-reference DTW comparison."""

    current_episode_id: str
    reference_episode_id: str
    backend_name: str = "DTWTrajectoryQualityBackend"


class DTWMedoidRequest(BaseModel):
    """Request for automatic reference selection."""

    episode_ids: list[str] = Field(default_factory=list)
    backend_name: str = "DTWTrajectoryQualityBackend"


class DTWSelectedStatsRequest(BaseModel):
    """Request for selected episode DTW statistics."""

    reference_episode_id: str
    episode_ids: list[str]
    backend_name: str = "DTWTrajectoryQualityBackend"


class QualityRouter:
    """Route container for trajectory quality APIs."""

    def __init__(
        self,
        session: EpisodeSession,
        backends: list[TrajectoryQualityBackend],
    ) -> None:
        """Initialize router with episode session and quality backends."""

        self.session = session
        self.backends = {backend.info().name: backend for backend in backends}
        self.router = APIRouter(prefix="/api/quality")
        self._register()

    def _register(self) -> None:
        """Register quality API routes."""

        self.router.add_api_route("/backends", self.list_backends, methods=["GET"])
        self.router.add_api_route("/dtw/compare", self.compare_dtw, methods=["POST"])
        self.router.add_api_route("/dtw/medoid-reference", self.find_medoid, methods=["POST"])
        self.router.add_api_route("/dtw/selected-stats", self.selected_stats, methods=["POST"])

    def list_backends(self) -> list[dict]:
        """Return quality backend metadata."""

        return [backend.info().model_dump() for backend in self.backends.values()]

    def compare_dtw(self, request: DTWCompareRequest) -> dict:
        """Compare one current episode against a reference episode."""

        try:
            backend = self._backend(request.backend_name)
            current = self.session.get_episode(request.current_episode_id)
            reference = self.session.get_episode(request.reference_episode_id)
            return backend.compare(current, reference).model_dump()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="episode not found") from exc
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    def find_medoid(self, request: DTWMedoidRequest) -> dict:
        """Choose a medoid reference from requested or active-source episodes."""

        try:
            backend = self._backend(request.backend_name)
            ids = request.episode_ids or [
                item["episode_id"] for item in self.session.list_episodes()
            ]
            episodes = [self.session.get_episode(episode_id) for episode_id in ids]
            medoid_id = backend.choose_medoid(episodes)
            metadata = self.session.get_metadata(medoid_id)
            return {"reference_episode_id": medoid_id, "title": metadata.title}
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="episode not found") from exc
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    def selected_stats(self, request: DTWSelectedStatsRequest) -> dict:
        """Aggregate selected episode DTW stats against one reference."""

        try:
            backend = self._backend(request.backend_name)
            reference = self.session.get_episode(request.reference_episode_id)
            episodes = [
                self.session.get_episode(episode_id)
                for episode_id in request.episode_ids
            ]
            return backend.selected_stats(episodes, reference).model_dump()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="episode not found") from exc
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    def _backend(self, name: str) -> TrajectoryQualityBackend:
        """Return a registered quality backend by name."""

        if name not in self.backends:
            raise KeyError(f"unknown quality backend: {name}")
        return self.backends[name]
