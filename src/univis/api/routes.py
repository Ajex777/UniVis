"""FastAPI routes for Phase 00 fake PolicyEpisode visualization."""

from __future__ import annotations

from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, Response

from univis.core.components import ComponentRegistry
from univis.core.episode_session import EpisodeSession
from univis.domain.policy_episode import Annotation
from univis.utils.color import color_for_key
from univis.utils.image_svg import make_camera_svg


class SourceSelectionRequest(BaseModel):
    """Request payload for switching episode source.

    Inputs:
        input_adapter: Registered adapter component name.
        root_path: Optional server-local file or directory path.
    Output:
        Validated source selection payload for route handlers.
    """

    input_adapter: str
    root_path: str = ""


class Phase00Router:
    """Route container for fake PolicyEpisode APIs.

    Inputs:
        repository: Fake in-memory PolicyEpisode repository.
    Output:
        A configured FastAPI router mounted by the application factory.
    """

    def __init__(
        self,
        session: EpisodeSession,
        registry: ComponentRegistry,
    ) -> None:
        """Initialize the router and register endpoints.

        Inputs:
            session: Current episode source context.
            registry: Component registry for adapter/exporter/backend metadata.
        Output:
            Router instance accessible through `self.router`.
        """

        self.session = session
        self.registry = registry
        self.router = APIRouter(prefix="/api")
        self._register()

    def _register(self) -> None:
        """Register API routes.

        Inputs:
            None.
        Output:
            Mutates `self.router` by adding endpoints.
        """

        self.router.add_api_route("/episodes", self.list_episodes, methods=["GET"])
        self.router.add_api_route("/registry", self.get_registry, methods=["GET"])
        self.router.add_api_route("/source", self.set_source, methods=["POST"])
        self.router.add_api_route(
            "/episodes/{episode_id}/metadata",
            self.get_metadata,
            methods=["GET"],
        )
        self.router.add_api_route(
            "/episodes/{episode_id}/trajectory",
            self.get_trajectory,
            methods=["GET"],
        )
        self.router.add_api_route(
            "/episodes/{episode_id}/annotation",
            self.update_annotation,
            methods=["PATCH"],
        )
        self.router.add_api_route(
            "/episodes/{episode_id}/frame/{camera_key}/{frame_index}",
            self.get_camera_frame,
            methods=["GET"],
        )

    def list_episodes(self) -> list[dict]:
        """Return fake episode list for the sidebar.

        Inputs:
            None.
        Output:
            List of metadata summaries as JSON-compatible dicts.
        """

        items: list[dict] = []
        try:
            items = self.session.list_episodes()
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return items

    def get_registry(self) -> dict:
        """Return registered fake adapter/exporter choices.

        Inputs:
            None.
        Output:
            Registry-like payload for UI dropdowns. Names mirror the future
            class registration model without importing real adapters yet.
        """

        return self.registry.api_payload()

    def set_source(self, request: SourceSelectionRequest) -> dict:
        """Switch the active episode source.

        Inputs:
            request: Adapter name and optional server-local root path.
        Output:
            Active source summary and fresh episode list.
        """

        root_path = request.root_path.strip() or None
        try:
            source = self.session.set_source(request.input_adapter, root_path)
            episodes = self.session.list_episodes()
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"source": source, "episodes": episodes}

    def get_metadata(self, episode_id: str) -> dict:
        """Return metadata for a selected episode.

        Inputs:
            episode_id: Stable fake episode id.
        Output:
            Metadata dict for viewer setup.
        """

        try:
            return self.session.get_metadata(episode_id).model_dump()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="episode not found") from exc
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    def get_trajectory(self, episode_id: str) -> dict:
        """Return synchronized trajectory arrays for visualization.

        Inputs:
            episode_id: Stable fake episode id.
        Output:
            JSON dict containing frame indices, timestamps, left/right xyz,
            gripper values, and reachability overlay.
        """

        try:
            episode = self.session.get_episode(episode_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="episode not found") from exc
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        frames = episode.frames
        return {
            "episode_id": episode_id,
            "indices": [frame.index for frame in frames],
            "timestamps": [frame.timestamp for frame in frames],
            "left_xyz": [frame.left.xyz for frame in frames],
            "right_xyz": [frame.right.xyz for frame in frames],
            "left_gripper": [frame.left.gripper for frame in frames],
            "right_gripper": [frame.right.gripper for frame in frames],
            "reachability": episode.metadata.reachability.model_dump()
            if episode.metadata.reachability
            else None,
        }

    def update_annotation(self, episode_id: str, annotation: Annotation) -> dict:
        """Persist in-memory annotation changes.

        Inputs:
            episode_id: Stable fake episode id.
            annotation: Replacement annotation payload.
        Output:
            Saved annotation dict.
        """

        try:
            saved = self.session.update_annotation(episode_id, annotation)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="episode not found") from exc
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return saved.model_dump()

    def get_camera_frame(
        self,
        episode_id: str,
        camera_key: str,
        frame_index: int,
    ) -> Response:
        """Return one generated camera frame as SVG.

        Inputs:
            episode_id: Stable fake episode id.
            camera_key: Camera stream key.
            frame_index: Synchronized frame index.
        Output:
            SVG image response.
        """

        try:
            meta = self.session.get_metadata(episode_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="episode not found") from exc
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        camera = next((cam for cam in meta.cameras if cam.key == camera_key), None)
        if camera is None:
            raise HTTPException(status_code=404, detail="camera not found")

        idx = max(0, min(int(frame_index), meta.num_frames - 1))
        svg = make_camera_svg(
            camera_key=camera_key,
            frame_index=idx,
            width=camera.width,
            height=camera.height,
            color=color_for_key(camera_key, idx),
            total_frames=meta.num_frames,
        )
        return Response(content=svg, media_type="image/svg+xml")
