"""Upload session management for browser-selected datasets."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path, PurePosixPath
from uuid import uuid4


@dataclass
class UploadRecord:
    """Tracks one browser dataset upload.

    Inputs:
        upload_id: Stable upload identifier.
        input_adapter: Adapter to use after upload completion.
        staging_root: Root directory where relative files are reconstructed.
        root_label: Browser-visible directory name.
        expected_files: Number of files reported by the browser.
        expected_bytes: Total byte size reported by the browser.
    Output:
        Mutable upload status stored by `UploadManager`.
    """

    upload_id: str
    input_adapter: str
    staging_root: Path
    root_label: str = ""
    expected_files: int = 0
    expected_bytes: int = 0
    received_files: int = 0
    received_bytes: int = 0
    status: str = "created"
    created_at: str = ""

    def payload(self) -> dict[str, object]:
        """Return a JSON-compatible upload summary."""

        return {
            "upload_id": self.upload_id,
            "input_adapter": self.input_adapter,
            "root_label": self.root_label,
            "staging_root": str(self.staging_root),
            "expected_files": self.expected_files,
            "expected_bytes": self.expected_bytes,
            "received_files": self.received_files,
            "received_bytes": self.received_bytes,
            "status": self.status,
            "created_at": self.created_at,
        }


class UploadManager:
    """Owns dataset uploads and staging directories.

    Inputs:
        uploads_root: Directory where upload sessions are stored.
    Output:
        Manager that creates sessions, writes files, and exposes scan roots.
    """

    def __init__(self, uploads_root: Path) -> None:
        """Initialize upload storage."""

        self.uploads_root = uploads_root
        self.uploads_root.mkdir(parents=True, exist_ok=True)
        self.records: dict[str, UploadRecord] = {}
        self._load_records()

    def create(
        self,
        input_adapter: str,
        root_label: str,
        expected_files: int,
        expected_bytes: int,
    ) -> UploadRecord:
        """Create a new upload session."""

        upload_id = uuid4().hex
        staging_root = self.uploads_root / upload_id / "dataset_root"
        staging_root.mkdir(parents=True, exist_ok=True)
        record = UploadRecord(
            upload_id=upload_id,
            input_adapter=input_adapter,
            root_label=root_label,
            staging_root=staging_root,
            expected_files=expected_files,
            expected_bytes=expected_bytes,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self.records[upload_id] = record
        self._save_record(record)
        return record

    def get(self, upload_id: str) -> UploadRecord:
        """Return one upload record or raise KeyError."""

        return self.records[upload_id]

    def write_file(self, upload_id: str, relative_path: str, data: bytes) -> Path:
        """Write one uploaded file into the staging directory."""

        record = self.get(upload_id)
        target = self._target_path(record.staging_root, relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        record.received_files += 1
        record.received_bytes += len(data)
        record.status = "uploading"
        self._save_record(record)
        return target

    def complete(self, upload_id: str) -> UploadRecord:
        """Mark an upload as complete."""

        record = self.get(upload_id)
        record.status = "completed"
        self._save_record(record)
        return record

    def scan_root(self, upload_id: str) -> Path:
        """Return the directory adapter scanning should use."""

        root = self.get(upload_id).staging_root
        hdf5_files = [p for p in root.iterdir() if p.suffix.lower() in {".hdf5", ".h5"}]
        children = [p for p in root.iterdir() if p.is_dir()]
        if not hdf5_files and len(children) == 1:
            return children[0]
        return root

    def list_sources(self) -> list[dict[str, object]]:
        """Return completed uploaded sources that still exist on disk."""

        sources: list[dict[str, object]] = []
        for record in sorted(
            self.records.values(),
            key=lambda item: item.created_at,
            reverse=True,
        ):
            if record.status != "completed":
                continue
            scan_root = self.scan_root(record.upload_id)
            if not scan_root.exists():
                continue
            payload = record.payload()
            payload["scan_root"] = str(scan_root)
            sources.append(payload)
        return sources

    def _target_path(self, staging_root: Path, relative_path: str) -> Path:
        """Resolve a browser relative path safely under staging_root."""

        path = PurePosixPath(relative_path.replace("\\", "/"))
        if path.is_absolute() or not path.parts:
            raise ValueError(f"invalid relative path: {relative_path}")
        if any(part in {"", ".", ".."} for part in path.parts):
            raise ValueError(f"unsafe relative path: {relative_path}")
        target = staging_root.joinpath(*path.parts).resolve()
        root = staging_root.resolve()
        if root not in target.parents and target != root:
            raise ValueError(f"path escapes staging root: {relative_path}")
        return target

    def _manifest_path(self, record: UploadRecord) -> Path:
        return record.staging_root.parent / "manifest.json"

    def _save_record(self, record: UploadRecord) -> None:
        manifest = self._manifest_path(record)
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(
            json.dumps(record.payload(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _load_records(self) -> None:
        for manifest in self.uploads_root.glob("*/manifest.json"):
            try:
                payload = json.loads(manifest.read_text(encoding="utf-8"))
                record = UploadRecord(
                    upload_id=str(payload["upload_id"]),
                    input_adapter=str(payload["input_adapter"]),
                    staging_root=Path(str(payload["staging_root"])),
                    root_label=str(payload.get("root_label", "")),
                    expected_files=int(payload.get("expected_files", 0)),
                    expected_bytes=int(payload.get("expected_bytes", 0)),
                    received_files=int(payload.get("received_files", 0)),
                    received_bytes=int(payload.get("received_bytes", 0)),
                    status=str(payload.get("status", "created")),
                    created_at=str(payload.get("created_at", "")),
                )
                self.records[record.upload_id] = record
            except Exception:
                continue
