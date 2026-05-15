"""FastAPI routes for PolicyEpisode visualization."""

from __future__ import annotations

import base64

from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, Query, Response

from univis.core.components import ComponentRegistry
from univis.core.episode_session import EpisodeSession
from univis.domain.policy_episode import Annotation


class SourceSelectionRequest(BaseModel):
    """Request payload for switching or validating an episode source."""

    input_adapter: str
    root_path: str = ""


class Phase00Router:
    """Route container for PolicyEpisode APIs."""

    def __init__(
        self,
        session: EpisodeSession,
        registry: ComponentRegistry,
    ) -> None:
        """Initialize the router with session and component registry."""
        self.session = session
        self.registry = registry
        self.router = APIRouter(prefix="/api")
        self._register()

    def _register(self) -> None:
        """Register API routes."""
        self.router.add_api_route("/episodes", self.list_episodes, methods=["GET"])
        self.router.add_api_route("/registry", self.get_registry, methods=["GET"])
        self.router.add_api_route("/source/validate", self.validate_source, methods=["POST"])
        self.router.add_api_route("/source", self.set_source, methods=["POST"])
        self.router.add_api_route("/episodes/{episode_id}/metadata", self.get_metadata, methods=["GET"])
        self.router.add_api_route("/episodes/{episode_id}/trajectory", self.get_trajectory, methods=["GET"])
        self.router.add_api_route("/episodes/{episode_id}/annotation", self.update_annotation, methods=["PATCH"])
        self.router.add_api_route(
            "/episodes/{episode_id}/frame/{camera_key}/{frame_index}",
            self.get_camera_frame,
            methods=["GET"],
        )
        self.router.add_api_route(
            "/episodes/{episode_id}/frames/{camera_key}",
            self.get_camera_frames,
            methods=["GET"],
        )

    def list_episodes(self) -> list[dict]:
        """Return episode list for the sidebar."""

        items: list[dict] = []
        try:
            items = self.session.list_episodes()
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return items

    def get_registry(self) -> dict:
        """Return registered adapter/exporter/backend choices."""

        return self.registry.api_payload()

    def set_source(self, request: SourceSelectionRequest) -> dict:
        """Switch the active episode source."""
        root_path = request.root_path.strip() or None
        try:
            source = self.session.set_source(request.input_adapter, root_path)
            episodes = self.session.list_episodes()
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"source": source, "episodes": episodes}

    def validate_source(self, request: SourceSelectionRequest) -> dict:
        """Validate an input adapter and root path without switching source."""

        root_path = request.root_path.strip() or None
        try:
            return self.session.validate_source(request.input_adapter, root_path)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    def get_metadata(self, episode_id: str) -> dict:
        """Return metadata for a selected episode."""
        try:
            return self.session.get_metadata(episode_id).model_dump()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="episode not found") from exc
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    def get_trajectory(self, episode_id: str) -> dict:
        """Return synchronized trajectory arrays for visualization."""
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
        """Persist annotation changes through the active adapter."""
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
        """Return one adapter frame with cache-busting headers.

        The endpoint uses `Cache-Control: max-age=0, must-revalidate`
        so browsers revalidate every frame URL on each src change,
        even under rapid autoplay intervals.
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
        try:
            image = self.session.get_image_frame(episode_id, camera_key, idx)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return Response(
            content=image.data,
            media_type=image.media_type,
            headers={"Cache-Control": "max-age=0, must-revalidate"},
        )

    def get_camera_frames(
        self,
        episode_id: str,
        camera_key: str,
        start: int = Query(default=0, ge=0),
        count: int = Query(default=50, ge=1, le=100),
    ) -> dict:
        """Return a contiguous base64 PNG batch for playback prefetch."""

        try:
            meta = self.session.get_metadata(episode_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="episode not found") from exc
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        camera = next((cam for cam in meta.cameras if cam.key == camera_key), None)
        if camera is None:
            raise HTTPException(status_code=404, detail="camera not found")

        start_idx = max(0, min(int(start), meta.num_frames - 1))
        batch_count = min(int(count), meta.num_frames - start_idx)
        try:
            images = self.session.get_image_frames(
                episode_id, camera_key, start_idx, batch_count
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {
            "episode_id": episode_id,
            "camera_key": camera_key,
            "start": start_idx,
            "count": len(images),
            "frames": [
                {
                    "index": start_idx + offset,
                    "media_type": image.media_type,
                    "data": base64.b64encode(image.data).decode("ascii"),
                }
                for offset, image in enumerate(images)
            ],
        }
