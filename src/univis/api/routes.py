"""FastAPI routes for Phase 00 fake PolicyEpisode visualization."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response

from univis.data.fake_policy_episode import FakePolicyEpisodeRepository
from univis.domain.policy_episode import Annotation
from univis.utils.color import color_for_key
from univis.utils.image_svg import make_camera_svg


class Phase00Router:
    """Route container for fake PolicyEpisode APIs.

    Inputs:
        repository: Fake in-memory PolicyEpisode repository.
    Output:
        A configured FastAPI router mounted by the application factory.
    """

    def __init__(self, repository: FakePolicyEpisodeRepository) -> None:
        """Initialize the router and register endpoints.

        Inputs:
            repository: Data source for fake episodes and annotations.
        Output:
            Router instance accessible through `self.router`.
        """

        self.repository = repository
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
        for meta in self.repository.list_metadata():
            item = meta.model_dump()
            item["conversion"] = self.repository.conversion_state(meta.episode_id)
            items.append(item)
        return items

    def get_registry(self) -> dict:
        """Return registered fake adapter/exporter choices.

        Inputs:
            None.
        Output:
            Registry-like payload for UI dropdowns. Names mirror the future
            class registration model without importing real adapters yet.
        """

        return {
            "input_adapters": [
                {
                    "name": "FakePolicyEpisodeAdapter",
                    "label": "Fake PolicyEpisode",
                    "description": "In-memory fake data for Phase 001.",
                },
                {
                    "name": "HDF5EpisodeAdapter",
                    "label": "HDF5 Episode",
                    "description": "Planned adapter for converted HDF5 files.",
                },
                {
                    "name": "PikaRawEpisodeAdapter",
                    "label": "PIKA Raw",
                    "description": "Planned adapter for PIKA raw episode folders.",
                },
            ],
            "output_exporters": [
                {
                    "name": "HDF5EpisodeExporter",
                    "label": "Compressed HDF5",
                    "description": "Planned first exporter implementation.",
                }
            ],
        }

    def get_metadata(self, episode_id: str) -> dict:
        """Return metadata for a selected episode.

        Inputs:
            episode_id: Stable fake episode id.
        Output:
            Metadata dict for viewer setup.
        """

        try:
            return self.repository.get_metadata(episode_id).model_dump()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="episode not found") from exc

    def get_trajectory(self, episode_id: str) -> dict:
        """Return synchronized trajectory arrays for visualization.

        Inputs:
            episode_id: Stable fake episode id.
        Output:
            JSON dict containing frame indices, timestamps, left/right xyz,
            gripper values, and reachability overlay.
        """

        try:
            episode = self.repository.get_episode(episode_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="episode not found") from exc

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
            saved = self.repository.update_annotation(episode_id, annotation)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="episode not found") from exc
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
            meta = self.repository.get_metadata(episode_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="episode not found") from exc

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
