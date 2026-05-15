"""FastAPI routes for local named workspaces."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from univis.core.episode_session import EpisodeSession
from univis.core.workspaces import WorkspaceManager


class WorkspaceSourceRequest(BaseModel):
    """Request payload for activating a workspace path.

    Inputs:
        workspace: Configured workspace name.
        relative_path: Path relative to the workspace root.
        input_adapter: Adapter used to scan the resolved local path.
    Output:
        Validated request for local-first source switching.
    """

    workspace: str
    relative_path: str = ""
    input_adapter: str


class WorkspaceRouter:
    """Route container for named workspace browsing and activation."""

    def __init__(self, manager: WorkspaceManager, session: EpisodeSession) -> None:
        """Initialize workspace routes."""

        self.manager = manager
        self.session = session
        self.router = APIRouter(prefix="/api/workspaces")
        self._register()

    def _register(self) -> None:
        """Register workspace endpoints."""

        self.router.add_api_route("", self.list_workspaces, methods=["GET"])
        self.router.add_api_route("/{workspace_name}/children", self.list_children, methods=["GET"])
        self.router.add_api_route("/source", self.activate_source, methods=["POST"])

    def list_workspaces(self) -> list[dict[str, object]]:
        """Return configured local workspaces."""

        return self.manager.list_workspaces()

    def list_children(
        self,
        workspace_name: str,
        path: str = Query(default=""),
    ) -> dict[str, object]:
        """Return one workspace directory listing."""

        try:
            return self.manager.list_children(workspace_name, path)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    def activate_source(self, request: WorkspaceSourceRequest) -> dict:
        """Switch active source to a server-local workspace path."""

        try:
            root_path = self.manager.resolve(request.workspace, request.relative_path)
            source = self.session.set_source(request.input_adapter, str(root_path))
            episodes = self.session.list_episodes()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {
            "mode": "workspace",
            "workspace": request.workspace,
            "relative_path": request.relative_path,
            "source": source,
            "episodes": episodes,
        }
