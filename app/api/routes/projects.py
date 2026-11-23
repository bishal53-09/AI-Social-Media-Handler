from __future__ import annotations

from datetime import date as date_type

from fastapi import APIRouter, Query, status

from app.api.deps import MediaServiceDep, ProjectServiceDep
from app.schemas.media import MediaList, ScanRequest, ScanResult
from app.schemas.project import (
    DayList,
    DayRead,
    DaySummary,
    ProjectCreate,
    ProjectDetail,
    ProjectList,
    ProjectRead,
    ProjectSettings,
)
from app.tracking.repository import validate_day_string

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=ProjectList)
def list_projects(svc: ProjectServiceDep) -> ProjectList:
    items = svc.list_projects()
    return ProjectList(items=[ProjectRead.model_validate(p) for p in items], total=len(items))


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(body: ProjectCreate, svc: ProjectServiceDep) -> ProjectRead:
    project = svc.init_project(
        body.name,
        body.path,
        description=body.description,
        default_camera=body.default_camera,
        enforce_roots=True,
    )
    return ProjectRead.model_validate(project)


@router.get("/{project_id}", response_model=ProjectDetail)
def get_project(project_id: str, svc: ProjectServiceDep) -> ProjectDetail:
    from pathlib import Path

    project = svc.get(project_id)
    repo = svc.repository(project)
    exists = Path(project.path).is_dir() and repo.exists()
    settings = None
    if exists:
        settings = ProjectSettings.model_validate(repo.read_project().get("settings") or {})
    days, media = svc.counts(project) if exists else (0, 0)
    return ProjectDetail(
        **ProjectRead.model_validate(project).model_dump(),
        exists_on_disk=exists,
        settings=settings,
        day_count=days,
        media_count=media,
    )


@router.get("/{project_id}/days", response_model=DayList)
def list_days(project_id: str, svc: ProjectServiceDep) -> DayList:
    project = svc.get(project_id)
    items = [DaySummary(**d) for d in svc.repository(project).list_days()]
    return DayList(items=items)


@router.get("/{project_id}/days/{day}", response_model=DayRead)
def get_day(project_id: str, day: date_type, svc: ProjectServiceDep) -> DayRead:
    project = svc.get(project_id)
    doc = svc.repository(project).read_day(validate_day_string(day.isoformat()))
    return DayRead(date=day, project_id=doc["project_id"], notes=doc.get("notes"), clips=doc["clips"])


@router.get("/{project_id}/media", response_model=MediaList)
def list_media(
    project_id: str,
    svc: ProjectServiceDep,
    media: MediaServiceDep,
    kind: str | None = Query(default=None, pattern="^(video|image)$"),
    stage: str | None = Query(default=None, max_length=32),
    day: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MediaList:
    svc.get(project_id)
    items, total = media.list_assets(project_id, kind=kind, stage=stage, day=day, limit=limit, offset=offset)
    return MediaList(items=items, total=total, limit=limit, offset=offset)  # type: ignore[arg-type]


@router.post("/{project_id}/media/scan", response_model=ScanResult)
def scan_media(
    project_id: str, svc: ProjectServiceDep, media: MediaServiceDep, body: ScanRequest | None = None
) -> ScanResult:
    """Index media files (and run ffprobe). Synchronous; long work such as proxies
    runs as a job (``POST /jobs``)."""
    project = svc.get(project_id)
    return media.scan(project, probe=(body.probe if body else True))
