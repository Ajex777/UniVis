"""FastAPI routes for episode conversion workflows."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from univis.core.conversions import ConversionService


class ConversionRequest(BaseModel):
    """Request payload for single or batch conversion.

    Inputs:
        exporter_name: Registered exporter component name.
        output_root: Optional server-local output directory.
    Output:
        Validated conversion request.
    """

    exporter_name: str
    output_root: str = ""


class ConversionRouter:
    """Route container for conversion APIs."""

    def __init__(self, service: ConversionService) -> None:
        """Initialize conversion routes."""

        self.service = service
        self.router = APIRouter(prefix="/api/conversions")
        self._register()

    def _register(self) -> None:
        """Register conversion endpoints."""

        self.router.add_api_route(
            "/episodes/{episode_id}",
            self.convert_episode,
            methods=["POST"],
        )
        self.router.add_api_route("/accepted", self.convert_accepted, methods=["POST"])
        self.router.add_api_route("/jobs", self.list_jobs, methods=["GET"])
        self.router.add_api_route("/jobs/{job_id}", self.get_job, methods=["GET"])

    def convert_episode(self, episode_id: str, request: ConversionRequest) -> dict:
        """Convert one active episode."""

        try:
            job = self.service.start_episode(
                episode_id,
                request.exporter_name,
                self._output_root(request),
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return job.model_dump()

    def convert_accepted(self, request: ConversionRequest) -> dict:
        """Convert all accepted episodes from the active source."""

        try:
            job = self.service.start_accepted(
                request.exporter_name,
                self._output_root(request),
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return job.model_dump()

    def list_jobs(self) -> list[dict]:
        """Return known conversion jobs."""

        return [job.model_dump() for job in self.service.list_jobs()]

    def get_job(self, job_id: str) -> dict:
        """Return one conversion job."""

        try:
            return self.service.get_job(job_id).model_dump()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    def _output_root(self, request: ConversionRequest) -> Path | None:
        raw = request.output_root.strip()
        return Path(raw).expanduser() if raw else None
