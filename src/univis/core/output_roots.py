"""Safe export root resolution for UniVis conversion jobs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath


@dataclass(frozen=True)
class OutputRoot:
    """Configured server-local root for exported datasets."""

    root: Path

    def payload(self) -> dict[str, str]:
        """Return a JSON-compatible description for the frontend."""

        return {"root": str(self.root)}


class OutputRootManager:
    """Resolve UI-provided output subpaths under one configured export root."""

    def __init__(self, root: Path | str) -> None:
        """Initialize the manager with a server-local export root."""

        self.output_root = OutputRoot(Path(root).expanduser().resolve())

    def config(self) -> dict[str, str]:
        """Return public output configuration."""

        return self.output_root.payload()

    def resolve(self, subpath: str = "") -> Path:
        """Resolve a relative UI subpath without allowing root escape."""

        clean = self._clean_subpath(subpath)
        target = self.output_root.root.joinpath(*clean.parts).resolve() if clean.parts else self.output_root.root
        if target != self.output_root.root and self.output_root.root not in target.parents:
            raise ValueError(f"output path escapes configured root: {subpath}")
        return target

    def _clean_subpath(self, subpath: str) -> PurePosixPath:
        """Normalize the browser-entered path into safe relative parts."""

        raw = subpath.strip().replace("\\", "/")
        if not raw:
            return PurePosixPath()
        if raw.startswith("/") or Path(raw).is_absolute():
            raise ValueError("output subpath must be relative to the configured output root")
        parts = [part for part in PurePosixPath(raw).parts if part not in {"", "."}]
        if any(part == ".." for part in parts):
            raise ValueError("output subpath cannot contain '..'")
        return PurePosixPath(*parts)
