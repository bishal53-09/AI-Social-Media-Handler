from __future__ import annotations

from fastapi import APIRouter, Query, status

from app.api.deps import JobServiceDep
from app.schemas.job import JobCreate, JobDetail, JobEventRead, JobList, JobRead, JobStatus

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=JobList)
def list_jobs(
    svc: JobServiceDep,
    status_: JobStatus | None = Query(default=None, alias="status"),
    project_id: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> JobList:
    items, total = svc.list_jobs(status=status_, project_id=project_id, limit=limit, offset=offset)
    return JobList(items=[JobRead.model_validate(j) for j in items], total=total)


@router.post("", response_model=JobRead, status_code=status.HTTP_202_ACCEPTED)
def create_job(body: JobCreate, svc: JobServiceDep) -> JobRead:
    return JobRead.model_validate(svc.create(body))


@router.get("/{job_id}", response_model=JobDetail)
def get_job(job_id: str, svc: JobServiceDep) -> JobDetail:
    job = svc.get(job_id)
    return JobDetail(
        **JobRead.model_validate(job).model_dump(),
        events=[JobEventRead.model_validate(e) for e in svc.events(job_id)],
    )


@router.post("/{job_id}/cancel", response_model=JobRead)
def cancel_job(job_id: str, svc: JobServiceDep) -> JobRead:
    return JobRead.model_validate(svc.cancel(job_id))
