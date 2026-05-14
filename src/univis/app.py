"""Application factory and CLI entrypoint for UniVis."""

from __future__ import annotations

import argparse
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from univis.api.routes import Phase00Router
from univis.api.uploads import UploadRouter
from univis.adapters.fake_policy_episode import FakePolicyEpisodeAdapter
from univis.adapters.hdf5 import HDF5EpisodeAdapter
from univis.core.components import ComponentRegistry
from univis.core.episode_session import EpisodeSession
from univis.core.uploads import UploadManager
from univis.data.fake_policy_episode import FakePolicyEpisodeRepository
from univis.exporters.hdf5 import HDF5EpisodeExporter
from univis.exporters.mock import MockEpisodeExporter
from univis.reachability.mock import MockReachabilityBackend


class UniVisAppContext:
    """Owns application dependencies for the Phase 00 server.

    Inputs:
        static_dir: Directory containing frontend static files.
    Output:
        Context object that can build a configured FastAPI application.
    """

    def __init__(
        self,
        static_dir: Path | None = None,
        uploads_root: Path | None = None,
    ) -> None:
        """Initialize dependency context.

        Inputs:
            static_dir: Optional override for static frontend files.
            uploads_root: Optional override for dataset upload staging.
        Output:
            Context with repository and static file path.
        """

        package_dir = Path(__file__).resolve().parent
        self.static_dir = static_dir or package_dir / "web" / "static"
        self.uploads_root = uploads_root or package_dir.parents[1] / ".univis" / "uploads"
        self.repository = FakePolicyEpisodeRepository()
        self.fake_adapter = FakePolicyEpisodeAdapter(self.repository)
        self.hdf5_adapter = HDF5EpisodeAdapter()
        self.adapters = [self.fake_adapter, self.hdf5_adapter]
        self.session = EpisodeSession(
            adapters=self.adapters,
            default_adapter_name=self.fake_adapter.info().name,
        )
        self.registry = ComponentRegistry(
            input_adapters=self.adapters,
            output_exporters=[HDF5EpisodeExporter(), MockEpisodeExporter()],
            reachability_backends=[MockReachabilityBackend()],
        )
        self.upload_manager = UploadManager(self.uploads_root)

    def create_app(self) -> FastAPI:
        """Create the FastAPI application.

        Inputs:
            None.
        Output:
            Configured FastAPI app serving API and frontend assets.
        """

        app = FastAPI(title="UniVis", version="0.1.0")
        app.include_router(Phase00Router(self.session, self.registry).router)
        app.include_router(UploadRouter(self.upload_manager, self.session).router)
        app.mount("/static", StaticFiles(directory=str(self.static_dir)), name="static")

        @app.get("/", include_in_schema=False)
        def index() -> FileResponse:
            """Serve the single-page frontend.

            Inputs:
                None.
            Output:
                `index.html` file response.
            """

            return FileResponse(self.static_dir / "index.html")

        return app


def create_app(uploads_root: Path | None = None) -> FastAPI:
    """Build a UniVis FastAPI app with default context.

    Inputs:
        None.
    Output:
        Configured FastAPI application.
    """

    return UniVisAppContext(uploads_root=uploads_root).create_app()


app = create_app()


def main() -> None:
    """Run the development server.

    Inputs:
        Optional `--host`, `--port`, and `--reload` CLI arguments.
    Output:
        Starts a local ASGI server process.
    """

    parser = argparse.ArgumentParser(description="Run UniVis Phase 00 server.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8010)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()
    uvicorn.run(
        "univis.app:app",
        host=str(args.host),
        port=int(args.port),
        reload=bool(args.reload),
    )


if __name__ == "__main__":
    main()
