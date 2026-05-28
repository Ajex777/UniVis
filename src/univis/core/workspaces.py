"""Named workspace management for local-first data access."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath


@dataclass(frozen=True)
class Workspace:
    """One server-visible root directory.

    Inputs:
        name: Stable workspace identifier shown in the UI.
        root: Absolute root path on the server host.
    Output:
        Immutable workspace config used for safe path resolution.
    """

    name: str
    root: Path

    def payload(self) -> dict[str, object]:
        """Return a JSON-compatible workspace summary."""

        return {"name": self.name, "root": str(self.root), "exists": self.root.exists()}


class WorkspaceManager:
    """Resolve and browse configured local workspaces.

    Inputs:
        roots: Mapping from workspace name to server-local path.
    Output:
        Manager that exposes safe relative browsing and path activation.
    """

    def __init__(self, roots: dict[str, Path | str] | None = None) -> None:
        """Initialize configured workspaces."""

        self.workspaces = {
            self._clean_name(name): Workspace(
                name=self._clean_name(name),
                root=Path(path).expanduser().resolve(),
            )
            for name, path in (roots or {}).items()
        }

    def list_workspaces(self) -> list[dict[str, object]]:
        """Return all configured workspaces."""

        return [item.payload() for item in self.workspaces.values()]

    def list_children(self, workspace_name: str, relative_path: str = "") -> dict[str, object]:
        """List direct children under a workspace-relative directory.

        Inputs:
            workspace_name: Configured workspace name.
            relative_path: Optional POSIX-style relative directory.
        Output:
            JSON-compatible directory listing with safe relative paths.
        """

        workspace = self._workspace(workspace_name)
        current = self.resolve(workspace.name, relative_path)
        if not current.is_dir():
            raise NotADirectoryError(f"workspace path is not a directory: {relative_path}")
        entries = []
        for child in sorted(current.iterdir(), key=lambda path: (not path.is_dir(), path.name)):
            if child.name.startswith("."):
                continue
            entry_path = self._relative_to_root(workspace, child)
            entries.append(
                {
                    "name": child.name,
                    "relative_path": entry_path,
                    "kind": "directory" if child.is_dir() else "file",
                    "selectable": child.is_dir() or child.suffix.lower() in {".hdf5", ".h5"},
                }
            )
        return {
            "workspace": workspace.payload(),
            "path": self._normalize_relative(relative_path),
            "parent_path": self._parent_relative(relative_path),
            "entries": entries,
        }

    def resolve(self, workspace_name: str, relative_path: str = "") -> Path:
        """Resolve a workspace-relative path without allowing root escape."""

        workspace = self._workspace(workspace_name)
        rel = self._normalize_relative(relative_path)
        target = workspace.root.joinpath(*PurePosixPath(rel).parts).resolve() if rel else workspace.root
        root = workspace.root.resolve()
        if target != root and root not in target.parents:
            raise ValueError(f"path escapes workspace: {relative_path}")
        return target

    def _workspace(self, name: str) -> Workspace:
        clean = self._clean_name(name)
        if clean not in self.workspaces:
            raise KeyError(f"unknown workspace: {name}")
        return self.workspaces[clean]

    def _relative_to_root(self, workspace: Workspace, path: Path) -> str:
        return path.resolve().relative_to(workspace.root.resolve()).as_posix()

    def _parent_relative(self, relative_path: str) -> str:
        rel = self._normalize_relative(relative_path)
        if not rel:
            return ""
        parent = PurePosixPath(rel).parent
        return "" if str(parent) == "." else parent.as_posix()

    def _normalize_relative(self, relative_path: str) -> str:
        raw = str(relative_path or "").replace("\\", "/").strip("/")
        path = PurePosixPath(raw)
        if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
            raise ValueError(f"invalid workspace path: {relative_path}")
        return path.as_posix() if raw else ""

    def _clean_name(self, name: str) -> str:
        clean = str(name).strip()
        if not clean or "/" in clean or "\\" in clean:
            raise ValueError(f"invalid workspace name: {name}")
        return clean
