"""FastAPI routes for browser dataset uploads."""

from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from univis.core.episode_session import EpisodeSession
from univis.core.uploads import UploadManager


class CreateUploadRequest(BaseModel):
    """Request payload for creating an upload session.

    Inputs:
        input_adapter: Adapter that should scan the uploaded staging directory.
        root_label: Browser-visible selected directory name.
        file_count: Number of files selected by the browser.
        total_size: Total selected byte size.
    Output:
        Validated upload session request.
    """

    input_adapter: str
    root_label: str = ""
    file_count: int = Field(default=0, ge=0)
    total_size: int = Field(default=0, ge=0)


class UploadRouter:
    """Route container for upload session APIs.

    Inputs:
        manager: Upload session manager.
        session: Active episode source context.
    Output:
        Configured router mounted under `/api/uploads`.
    """

    def __init__(self, manager: UploadManager, session: EpisodeSession) -> None:
        """Initialize upload routes."""

        self.manager = manager
        self.session = session
        self.router = APIRouter(prefix="/api/uploads")
        self._register()

    def _register(self) -> None:
        """Register upload endpoints."""

        self.router.add_api_route("/datasets", self.create_dataset, methods=["POST"])
        self.router.add_api_route("/{upload_id}", self.get_upload, methods=["GET"])
        self.router.add_api_route("/{upload_id}/files", self.upload_files, methods=["POST"])
        self.router.add_api_route(
            "/{upload_id}/complete",
            self.complete_upload,
            methods=["POST"],
        )

    def create_dataset(self, request: CreateUploadRequest) -> dict:
        """Create an upload session."""

        try:
            record = self.manager.create(
                input_adapter=request.input_adapter,
                root_label=request.root_label,
                expected_files=request.file_count,
                expected_bytes=request.total_size,
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return record.payload()

    def get_upload(self, upload_id: str) -> dict:
        """Return upload status."""

        try:
            return self.manager.get(upload_id).payload()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="upload not found") from exc

    async def upload_files(
        self,
        upload_id: str,
        files: list[UploadFile] = File(...),
        relative_paths: list[str] = Form(...),
    ) -> dict:
        """Upload one batch of files while preserving relative paths."""

        if len(files) != len(relative_paths):
            raise HTTPException(status_code=400, detail="files/relative_paths mismatch")
        try:
            for upload_file, relative_path in zip(files, relative_paths):
                data = await upload_file.read()
                self.manager.write_file(upload_id, relative_path, data)
            return self.manager.get(upload_id).payload()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="upload not found") from exc
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    def complete_upload(self, upload_id: str) -> dict:
        """Complete upload and switch the active viewer source."""

        try:
            record = self.manager.complete(upload_id)
            scan_root = self.manager.scan_root(upload_id)
            source = self.session.set_source(record.input_adapter, str(scan_root))
            episodes = self.session.list_episodes()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="upload not found") from exc
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {
            "upload": record.payload(),
            "source": source,
            "episodes": episodes,
        }
