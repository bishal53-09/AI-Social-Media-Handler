"""HTTP API. ``api_router`` aggregates every route module under ``/api/v1``."""

from fastapi import APIRouter

from app.api.routes import health, jobs, posts, projects, settings

api_router = APIRouter(prefix="/api/v1")
for _module in (health, projects, jobs, posts, settings):
    api_router.include_router(_module.router)

__all__ = ["api_router"]
