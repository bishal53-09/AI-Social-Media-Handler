"""Pipeline orchestrator.

Runs an ordered list of stages over the media assets of a project, persisting
progress and a per-stage trace (``JobEvent``) to SQLite. Stages themselves are
pure with respect to the database; this module is the only place that maps
stage outputs onto ``MediaAsset`` rows.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import AppConfig
from app.core.exceptions import AppError, CancelledError, UnsupportedOperationError, ValidationFailedError
from app.core.security import redact
from app.database.base import utcnow
from app.models import Job, JobEvent, MediaAsset, Project
from app.pipeline.base import Stage, StageContext
from app.pipeline.stages._future import (
    AnalysisStage,
    AudioStage,
    ColorGradingStage,
    EditingStage,
    ReframingStage,
    RenderingStage,
    SubtitlesStage,
)
from app.pipeline.stages.ingest import IngestStage
from app.pipeline.stages.probe import ProbeStage
from app.pipeline.stages.proxies import ProxyStage
from app.pipeline.stages.thumbnails import ThumbnailStage
from app.pipeline.stages.validation import ValidationStage
from app.services.media_service import MediaService
from app.tracking.events import append_event

logger = logging.getLogger(__name__)

STAGES: dict[str, Stage] = {
    s.name: s
    for s in (
        IngestStage(),
        ProbeStage(),
        ThumbnailStage(),
        ProxyStage(),
        ValidationStage(),
        ColorGradingStage(),
        ReframingStage(),
        EditingStage(),
        SubtitlesStage(),
        AudioStage(),
        RenderingStage(),
        AnalysisStage(),
    )
}
DEFAULT_STAGES = ["ingest", "probe", "thumbnails", "proxies", "validation"]


def resolve_stages(names: list[str] | None) -> list[Stage]:
    """Validate requested stage names; refuse unknown or unimplemented stages."""
    names = names or DEFAULT_STAGES
    out: list[Stage] = []
    for n in names:
        stage = STAGES.get(n)
        if stage is None:
            raise ValidationFailedError(f"Unknown stage '{n}'.", details={"known": sorted(STAGES)})
        if not stage.implemented:
            raise UnsupportedOperationError(f"Stage '{n}' is not implemented yet.", details={"stage": n})
        out.append(stage)
    return out


class PipelineRunner:
    """Executes one ``pipeline.process`` job."""

    def __init__(self, session: Session, config: AppConfig) -> None:
        self.session = session
        self.config = config
        self._last_flush = 0.0
        self._last_cancel_check = 0.0
        self._cancel_cached = False

    # -- job bookkeeping ----------------------------------------------------

    def _event(
        self,
        job: Job,
        event: str,
        stage: str | None = None,
        message: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> None:
        self.session.add(
            JobEvent(job_id=job.id, stage=stage, event=event, message=redact(message) if message else None, data=data)
        )
        self.session.commit()

    def _cancelled(self, job: Job) -> bool:
        now = time.monotonic()
        if now - self._last_cancel_check > 0.4:
            self._last_cancel_check = now
            self.session.refresh(job)
            self._cancel_cached = job.cancel_requested
        return self._cancel_cached

    def _set_progress(self, job: Job, value: float, stage: str | None) -> None:
        job.progress = round(min(max(value, 0.0), 1.0), 4)
        job.current_stage = stage
        now = time.monotonic()
        if now - self._last_flush > 0.5:
            self._last_flush = now
            self.session.commit()

    # -- main ----------------------------------------------------------------

    def run(self, job_id: str) -> None:
        job = self.session.get(Job, job_id)
        if job is None or job.status != "queued":
            return
        job.status, job.started_at = "running", utcnow()
        self.session.commit()
        try:
            summary = self._process(job)
        except CancelledError:
            job.status, job.error = "cancelled", None
            self._event(job, "cancelled", message="Job cancelled.")
        except AppError as exc:
            job.status, job.error = "failed", redact(exc.message)
            self._event(job, "failed", message=exc.message, data=exc.details or None)
        except Exception as exc:
            logger.exception("Job %s crashed", job.id)
            job.status, job.error = "failed", redact(f"Unexpected error: {exc}")
            self._event(job, "failed", message=job.error)
        else:
            job.result = summary
            failed = summary["failed"]
            if failed:
                job.status = "failed"
                job.error = f"{failed} of {summary['total']} file(s) failed. See job events."
            else:
                job.status = "completed"
        job.finished_at = utcnow()
        if job.status == "completed":
            job.progress = 1.0
        self.session.commit()

    def _process(self, job: Job) -> dict[str, Any]:
        project = self.session.get(Project, job.project_id)
        if project is None:
            raise ValidationFailedError("Project no longer exists.")
        params = job.params or {}
        stages = resolve_stages(params.get("stages"))
        force = bool(params.get("force", False))
        root = Path(project.path)

        q = select(MediaAsset).where(
            MediaAsset.project_id == project.id,
            MediaAsset.missing.is_(False),
            MediaAsset.stage.in_(("raw", "stitched")),
        )
        if params.get("asset_ids"):
            q = q.where(MediaAsset.id.in_(params["asset_ids"]))
        assets = list(self.session.scalars(q.order_by(MediaAsset.relative_path)))
        self._event(
            job,
            "info",
            message=f"Processing {len(assets)} file(s).",
            data={"stages": [s.name for s in stages], "force": force},
        )

        summary: dict[str, Any] = {"total": len(assets), "succeeded": 0, "failed": 0, "assets": {}}
        for i, asset in enumerate(assets):
            outcome = self._process_asset(job, root, asset, stages, force, i, len(assets))
            summary["assets"][asset.id] = outcome
            summary["succeeded" if outcome["ok"] else "failed"] += 1
        MediaService(self.session, self.config).sync_day_files(project)
        append_event(
            root,
            "pipeline.completed",
            {
                "job_id": job.id,
                "succeeded": summary["succeeded"],
                "failed": summary["failed"],
            },
        )
        return summary

    def _process_asset(
        self,
        job: Job,
        root: Path,
        asset: MediaAsset,
        stages: list[Stage],
        force: bool,
        index: int,
        total: int,
    ) -> dict[str, Any]:
        ctx = StageContext(
            project_root=root,
            source_rel=asset.relative_path,
            kind=asset.kind,
            config=self.config,
            media_type=asset.media_type,
            force=force,
            is_cancelled=lambda: self._cancelled(job),
        )
        if asset.sha256:
            ctx.previous["ingest"] = {
                "sha256": asset.sha256,
                "size_bytes": asset.size_bytes,
                "mtime": asset.mtime,
            }
        if asset.probe:
            ctx.previous["probe"] = {"probe": asset.probe, "media_type": asset.media_type}
        if asset.thumbnail_path:
            ctx.previous["thumbnails"] = {"thumbnail": asset.thumbnail_path}
        if asset.proxy_path:
            ctx.previous["proxies"] = {"proxy": asset.proxy_path}

        outcome: dict[str, Any] = {"path": asset.relative_path, "ok": True, "stages": {}}
        for si, stage in enumerate(stages):
            if asset.kind not in stage.kinds:
                outcome["stages"][stage.name] = "not_applicable"
                continue
            base = (index + si / len(stages)) / total
            span = 1 / (total * len(stages))
            ctx.progress = self._progress_reporter(job, base, span, stage.name)
            self._set_progress(job, base, stage.name)
            self._event(job, "started", stage.name, asset.relative_path)
            try:
                res = stage.run(ctx)
            except CancelledError:
                raise
            except Exception as exc:
                msg = getattr(exc, "message", None) or str(exc)
                outcome.update(ok=False, error=redact(msg))
                outcome["stages"][stage.name] = "failed"
                self._event(
                    job, "failed", stage.name, f"{asset.relative_path}: {msg}", getattr(exc, "details", None) or None
                )
                if stage.name == "probe":
                    asset.probe_error = redact(msg)[:1000]
                    self.session.commit()
                return outcome
            ctx.previous[stage.name] = res.outputs
            self._apply(asset, stage.name, res.outputs)
            outcome["stages"][stage.name] = "skipped" if res.skipped else "completed"
            self._event(
                job,
                "skipped" if res.skipped else "completed",
                stage.name,
                res.message or asset.relative_path,
                {"file": asset.relative_path, "config": res.config_used, "outputs": res.outputs},
            )
        return outcome

    def _progress_reporter(self, job: Job, base: float, span: float, stage: str) -> Callable[[float, str | None], None]:
        def report(fraction: float, _message: str | None = None) -> None:
            self._set_progress(job, base + span * fraction, stage)

        return report

    def _apply(self, asset: MediaAsset, stage: str, out: dict[str, Any]) -> None:
        if stage == "ingest" and out.get("sha256"):
            asset.sha256, asset.size_bytes, asset.mtime = out["sha256"], out["size_bytes"], out["mtime"]
        elif stage == "probe":
            asset.probe, asset.probe_error = out["probe"], None
            asset.media_type, asset.camera = out["media_type"], out.get("camera") or asset.camera
        elif stage == "thumbnails" and out.get("thumbnail"):
            asset.thumbnail_path = out["thumbnail"]
        elif stage == "proxies" and out.get("proxy"):
            asset.proxy_path = out["proxy"]
        self.session.commit()


ProgressCallback = Callable[[float, str | None], None]
