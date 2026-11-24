from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, Query, status

from app.api.deps import JobServiceDep
from app.schemas.job import JobCreate, JobDetail, JobEventRead, JobList, JobRead, JobStatus
from app.services.listing import SortOrder

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=JobList)
def list_jobs(
    svc: JobServiceDep,
    status_: JobStatus | None = Query(default=None, alias="status"),
    project_id: str | None = None,
    type_: str | None = Query(default=None, alias="type", max_length=64),
    q: str | None = Query(default=None, max_length=100, description="Search in job type and id."),
    created_from: date | None = None,
    created_to: date | None = None,
    sort: Literal["created", "status", "type", "progress"] | None = None,
    order: SortOrder = "desc",
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> JobList:
    items, total = svc.list_jobs(
        status=status_,
        project_id=project_id,
        job_type=type_,
        q=q,
        created_from=created_from,
        created_to=created_to,
        sort=sort,
        order=order,
        limit=limit,
        offset=offset,
    )
    return JobList(items=[JobRead.model_validate(j) for j in items], total=total, limit=limit, offset=offset)


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
