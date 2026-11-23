"""HTTP API. ``api_router`` aggregates every route module under ``/api/v1``."""

from fastapi import APIRouter

from app.api.routes import analytics, content_posts, health, jobs, posts, projects, settings, system

api_router = APIRouter(prefix="/api/v1")
for _module in (health, projects, content_posts, jobs, posts, analytics, settings, system):
    api_router.include_router(_module.router)

__all__ = ["api_router"]
