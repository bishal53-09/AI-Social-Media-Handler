"""Job lifecycle: create, run in background threads, cancel, query."""

from __future__ import annotations

import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.config import AppConfig
from app.core.exceptions import AppError, ConflictError, NotFoundError, ValidationFailedError
from app.core.security import redact
from app.database.base import utcnow
from app.database.session import Database
from app.models import Job, JobEvent, Project
from app.pipeline.orchestrator import PipelineRunner, resolve_stages
from app.schemas.job import JobCreate
from app.services.listing import SortOrder, apply_sort, day_end_exclusive, day_start, like_pattern
from app.services.media_service import MediaService

logger = logging.getLogger(__name__)

TERMINAL = {"completed", "failed", "cancelled"}

#: Columns the job list can be sorted by (``?sort=``).
JOB_SORT = {"created": Job.created_at, "status": Job.status, "type": Job.type, "progress": Job.progress}


class JobRunner:
    """Runs jobs on a small thread pool. State lives in SQLite, not in memory."""

    def __init__(self, db: Database, config: AppConfig, max_workers: int = 2) -> None:
        self.db = db
        self.config = config
        self._pool = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="job")

    def recover_interrupted(self) -> int:
        """Mark jobs left running/queued by a previous process as failed."""
        with self.db.transaction() as s:
            jobs = list(s.scalars(select(Job).where(Job.status.in_(("queued", "running")))))
            for j in jobs:
                j.status, j.finished_at = "failed", utcnow()
                j.error = "Interrupted: the application stopped before this job finished."
            return len(jobs)

    def submit(self, job_id: str) -> None:
        self._pool.submit(self._run, job_id)

    def _run(self, job_id: str) -> None:
        session = self.db.session()
        try:
            job = session.get(Job, job_id)
            if job is None or job.status != "queued":
                return
            handler: Callable[[Session, Job], None] = {
                "media.scan": self._scan,
                "pipeline.process": lambda s, j: PipelineRunner(s, self.config).run(j.id),
            }.get(job.type, self._unknown)
            handler(session, job)
        except Exception:  # pragma: no cover - last-resort guard
            logger.exception("Job runner crashed for %s", job_id)
        finally:
            session.close()

    def _unknown(self, session: Session, job: Job) -> None:
        job.status, job.error, job.finished_at = "failed", f"Unknown job type {job.type}", utcnow()
        session.commit()

    def _scan(self, session: Session, job: Job) -> None:
        job.status, job.started_at = "running", utcnow()
        session.commit()
        try:
            project = session.get(Project, job.project_id)
            if project is None:
                raise NotFoundError("Project not found.")

            def cancelled() -> bool:
                session.refresh(job)
                return job.cancel_requested

            result = MediaService(session, self.config).scan(
                project, probe=bool((job.params or {}).get("probe", True)), is_cancelled=cancelled
            )
            job.result = result.model_dump()
            job.status = "cancelled" if job.cancel_requested else "completed"
            job.progress = 1.0
        except Exception as exc:
            session.rollback()
            session.refresh(job)
            job.status = "failed"
            job.error = redact(getattr(exc, "message", None) or str(exc))
        job.finished_at = utcnow()
        session.commit()

    def shutdown(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)


class JobService:
    def __init__(self, session: Session, runner: JobRunner | None = None) -> None:
        self.session = session
        self.runner = runner

    def create(self, req: JobCreate) -> Job:
        if self.session.get(Project, req.project_id) is None:
            raise NotFoundError(f"Project '{req.project_id}' not found.")
        params: dict[str, Any] = dict(req.params)
        if req.type == "pipeline.process":
            resolve_stages(params.get("stages"))  # rejects unknown / unimplemented stages
            if "asset_ids" in params and not isinstance(params["asset_ids"], list):
                raise ValidationFailedError("asset_ids must be a list.")
        job = Job(type=req.type, project_id=req.project_id, params=params)
        self.session.add(job)
        self.session.commit()
        if self.runner is not None:
            self.runner.submit(job.id)
        return job

    def get(self, job_id: str) -> Job:
        job = self.session.get(Job, job_id)
        if job is None:
            raise NotFoundError(f"Job '{job_id}' not found.")
        return job

    def events(self, job_id: str, limit: int = 500) -> list[JobEvent]:
        return list(
            self.session.scalars(
                select(JobEvent)
                .where(JobEvent.job_id == job_id)
                .order_by(JobEvent.created_at, JobEvent.id)
                .limit(limit)
            )
        )

    def list_jobs(
        self,
        *,
        status: str | None = None,
        project_id: str | None = None,
        job_type: str | None = None,
        q: str | None = None,
        created_from: date | None = None,
        created_to: date | None = None,
        sort: str | None = None,
        order: SortOrder = "desc",
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Job], int]:
        query = select(Job)
        if status:
            query = query.where(Job.status == status)
        if project_id:
            query = query.where(Job.project_id == project_id)
        if job_type:
            query = query.where(Job.type == job_type)
        if q and q.strip():
            pat = like_pattern(q)
            query = query.where(or_(Job.type.ilike(pat, escape="\\"), Job.id.ilike(pat, escape="\\")))
        if created_from:
            query = query.where(Job.created_at >= day_start(created_from))
        if created_to:
            query = query.where(Job.created_at < day_end_exclusive(created_to))
        total = self.session.scalar(select(func.count()).select_from(query.subquery())) or 0
        query = apply_sort(query, JOB_SORT, sort, order, [Job.created_at.desc()], Job.id)
        return list(self.session.scalars(query.limit(limit).offset(offset))), int(total)

    def cancel(self, job_id: str) -> Job:
        job = self.get(job_id)
        if job.status in TERMINAL:
            raise ConflictError(f"Job is already {job.status}.")
        job.cancel_requested = True
        if job.status == "queued":
            job.status, job.finished_at = "cancelled", utcnow()
        self.session.commit()
        return job


__all__ = ["AppError", "JobRunner", "JobService"]
