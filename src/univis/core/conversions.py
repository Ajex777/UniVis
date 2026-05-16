"""Conversion orchestration for active episode sources."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from threading import Lock, Thread
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from univis.adapters.base import EpisodeSource, RawEpisodeAdapter
from univis.core.episode_session import EpisodeSession
from univis.exporters.base import EpisodeExporter, ExportResult
from univis.utils.json_io import write_json


class ConversionItem(BaseModel):
    """Serializable result for one attempted episode conversion."""

    episode_id: str
    success: bool
    output_path: str = ""
    message: str = ""


class ConversionReport(BaseModel):
    """Batch conversion report written beside exported files."""

    exporter_name: str
    output_root: str
    total: int
    succeeded: int
    failed: int
    items: list[ConversionItem] = Field(default_factory=list)


class ConversionJob(BaseModel):
    """In-process background conversion job state."""

    job_id: str
    scope: str
    status: str = "queued"
    exporter_name: str
    output_root: str
    total: int
    completed: int = 0
    succeeded: int = 0
    failed: int = 0
    progress: float = 0.0
    message: str = ""
    items: list[ConversionItem] = Field(default_factory=list)
    created_at: str
    updated_at: str


class ConversionService:
    """Run active-source conversions through registered exporters."""

    def __init__(
        self,
        session: EpisodeSession,
        exporters: list[EpisodeExporter],
        default_output_root: Path,
    ) -> None:
        """Initialize conversion dependencies."""

        self.session = session
        self.exporters = {exporter.info().name: exporter for exporter in exporters}
        self.default_output_root = default_output_root
        self._jobs: dict[str, ConversionJob] = {}
        self._lock = Lock()

    def start_episode(
        self,
        episode_id: str,
        exporter_name: str,
        output_root: Path | None = None,
    ) -> ConversionJob:
        """Start one active episode conversion in the background."""

        return self._start([episode_id], "current", exporter_name, output_root)

    def start_accepted(
        self,
        exporter_name: str,
        output_root: Path | None = None,
    ) -> ConversionJob:
        """Start accepted-only active source conversion in the background."""

        ids = [
            item["episode_id"]
            for item in self.session.list_episodes()
            if item.get("annotation", {}).get("review_status") == "accepted"
        ]
        return self._start(ids, "accepted", exporter_name, output_root)

    def list_jobs(self) -> list[ConversionJob]:
        """Return recent conversion jobs, newest first."""

        with self._lock:
            return sorted(self._jobs.values(), key=lambda job: job.created_at, reverse=True)

    def get_job(self, job_id: str) -> ConversionJob:
        """Return one conversion job."""

        with self._lock:
            if job_id not in self._jobs:
                raise KeyError(f"conversion job not found: {job_id}")
            return self._jobs[job_id]

    def _start(
        self,
        episode_ids: list[str],
        scope: str,
        exporter_name: str,
        output_root: Path | None,
    ) -> ConversionJob:
        target_root = Path(output_root or self.default_output_root).expanduser().resolve()
        exporter = self._exporter(exporter_name)
        adapter = self.session.adapters[self.session.active.adapter_name]
        source = self.session.active.source
        now = self._now()
        job = ConversionJob(
            job_id=uuid4().hex,
            scope=scope,
            exporter_name=exporter.info().name,
            output_root=str(target_root),
            total=len(episode_ids),
            created_at=now,
            updated_at=now,
            message="queued",
        )
        with self._lock:
            self._jobs[job.job_id] = job
        Thread(
            target=self._run_job,
            args=(job.job_id, episode_ids, exporter, adapter, source, target_root),
            daemon=True,
        ).start()
        return job

    def _run_job(
        self,
        job_id: str,
        episode_ids: list[str],
        exporter: EpisodeExporter,
        adapter: RawEpisodeAdapter,
        source: EpisodeSource | None,
        output_root: Path,
    ) -> None:
        output_root.mkdir(parents=True, exist_ok=True)
        self._update_job(job_id, status="running", message="running")
        if not episode_ids:
            self._finish_job(job_id, exporter, output_root, adapter, source)
            return
        for episode_id in episode_ids:
            item = self._convert_one(episode_id, exporter, adapter, source, output_root)
            with self._lock:
                job = self._jobs[job_id]
                job.items.append(item)
                job.completed += 1
                job.succeeded += int(item.success)
                job.failed += int(not item.success)
                job.progress = job.completed / max(1, job.total)
                job.message = item.message
                job.updated_at = self._now()
        self._finish_job(job_id, exporter, output_root, adapter, source)

    def _convert_one(
        self,
        episode_id: str,
        exporter: EpisodeExporter,
        adapter: RawEpisodeAdapter,
        source: EpisodeSource | None,
        output_root: Path,
    ) -> ConversionItem:
        try:
            episode = adapter.load_episode(episode_id, source)
            bound = self._with_images(exporter, adapter, source)
            return self._item_from_result(bound.export(episode, output_root))
        except Exception as exc:
            return ConversionItem(episode_id=episode_id, success=False, message=str(exc))

    def _finish_job(
        self,
        job_id: str,
        exporter: EpisodeExporter,
        output_root: Path,
        adapter: RawEpisodeAdapter,
        source: EpisodeSource | None,
    ) -> None:
        with self._lock:
            job = self._jobs[job_id]
            report = ConversionReport(
                exporter_name=exporter.info().name,
                output_root=str(output_root),
                total=job.total,
                succeeded=job.succeeded,
                failed=job.failed,
                items=job.items,
            )
        write_json(output_root / "conversion_report.json", self._report_payload(report, adapter, source))
        status = "succeeded" if report.failed == 0 else "failed"
        self._update_job(job_id, status=status, progress=1.0, message=f"{report.succeeded}/{report.total} succeeded")

    def _exporter(self, exporter_name: str) -> EpisodeExporter:
        if exporter_name not in self.exporters:
            raise KeyError(f"unknown exporter: {exporter_name}")
        return self.exporters[exporter_name]

    def _with_images(
        self,
        exporter: EpisodeExporter,
        adapter: RawEpisodeAdapter,
        source: EpisodeSource | None,
    ) -> EpisodeExporter:
        binder = getattr(exporter, "with_image_provider", None)
        return binder(adapter, source) if callable(binder) else exporter

    def _update_job(self, job_id: str, **changes: object) -> None:
        with self._lock:
            job = self._jobs[job_id]
            for key, value in changes.items():
                setattr(job, key, value)
            job.updated_at = self._now()

    def _item_from_result(self, result: ExportResult) -> ConversionItem:
        return ConversionItem(
            episode_id=result.episode_id,
            success=result.success,
            output_path=result.output_path,
            message=result.message,
        )

    def _report_payload(
        self,
        report: ConversionReport,
        adapter: RawEpisodeAdapter,
        source: EpisodeSource | None,
    ) -> dict[str, Any]:
        payload = report.model_dump()
        payload["created_at"] = self._now()
        payload["input_adapter"] = adapter.info().name
        payload["input_root"] = str(source.root_path) if source and source.root_path else ""
        return payload

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()
