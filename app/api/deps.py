"""FastAPI dependencies."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.config import AppConfig, Settings
from app.database.session import Database
from app.services.content_post_service import ContentPostService
from app.services.engagement_service import EngagementService
from app.services.job_service import JobRunner, JobService
from app.services.media_service import MediaService
from app.services.post_service import PostService
from app.services.project_service import ProjectService


def get_db(request: Request) -> Database:
    return request.app.state.db


def get_session(request: Request) -> Iterator[Session]:
    session = request.app.state.db.session()
    try:
        yield session
    finally:
        session.close()


def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings


def get_config_dep(request: Request) -> AppConfig:
    return request.app.state.config


SessionDep = Annotated[Session, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
ConfigDep = Annotated[AppConfig, Depends(get_config_dep)]


def project_service(session: SessionDep, settings: SettingsDep, config: ConfigDep) -> ProjectService:
    return ProjectService(session, settings, config)


def media_service(session: SessionDep, config: ConfigDep) -> MediaService:
    return MediaService(session, config)


def job_service(request: Request, session: SessionDep) -> JobService:
    runner: JobRunner = request.app.state.job_runner
    return JobService(session, runner)


def post_service(session: SessionDep) -> PostService:
    return PostService(session)


def engagement_service(session: SessionDep, config: ConfigDep) -> EngagementService:
    return EngagementService(session, config)


def content_post_service(session: SessionDep, config: ConfigDep) -> ContentPostService:
    return ContentPostService(session, config)


ProjectServiceDep = Annotated[ProjectService, Depends(project_service)]
MediaServiceDep = Annotated[MediaService, Depends(media_service)]
JobServiceDep = Annotated[JobService, Depends(job_service)]
PostServiceDep = Annotated[PostService, Depends(post_service)]
EngagementServiceDep = Annotated[EngagementService, Depends(engagement_service)]
ContentPostServiceDep = Annotated[ContentPostService, Depends(content_post_service)]
