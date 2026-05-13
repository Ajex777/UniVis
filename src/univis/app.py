"""Application factory and CLI entrypoint for UniVis."""

from __future__ import annotations

import argparse
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from univis.api.routes import Phase00Router
from univis.data.fake_policy_episode import FakePolicyEpisodeRepository


class UniVisAppContext:
    """Owns application dependencies for the Phase 00 server.

    Inputs:
        static_dir: Directory containing frontend static files.
    Output:
        Context object that can build a configured FastAPI application.
    """

    def __init__(self, static_dir: Path | None = None) -> None:
        """Initialize dependency context.

        Inputs:
            static_dir: Optional override for static frontend files.
        Output:
            Context with repository and static file path.
        """

        package_dir = Path(__file__).resolve().parent
        self.static_dir = static_dir or package_dir / "web" / "static"
        self.repository = FakePolicyEpisodeRepository()

    def create_app(self) -> FastAPI:
        """Create the FastAPI application.

        Inputs:
            None.
        Output:
            Configured FastAPI app serving API and frontend assets.
        """

        app = FastAPI(title="UniVis", version="0.1.0")
        app.include_router(Phase00Router(self.repository).router)
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


def create_app() -> FastAPI:
    """Build a UniVis FastAPI app with default context.

    Inputs:
        None.
    Output:
        Configured FastAPI application.
    """

    return UniVisAppContext().create_app()


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
