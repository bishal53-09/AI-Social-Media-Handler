"""System information: whether a newer version of the app is available."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Query
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from app.api.deps import SettingsDep
from app.services.update_service import get_update_checker

router = APIRouter(prefix="/system", tags=["system"])


class UpdateStatusRead(BaseModel):
    supported: bool
    update_available: bool
    branch: str | None
    upstream: str | None
    local_commit: str | None
    remote_commit: str | None
    behind: int
    ahead: int
    dirty: bool
    fetched: bool
    checked_at: str
    command: str
    message: str


@router.get("/update", response_model=UpdateStatusRead)
async def update_status(
    settings: SettingsDep,
    refresh: bool = Query(False, description="Fetch from the remote now instead of using the cache."),
) -> UpdateStatusRead:
    """Compare the local checkout with its upstream. Never modifies the checkout."""
    checker = get_update_checker()
    status = await run_in_threadpool(checker.check, fetch=settings.update_check, force=refresh)
    return UpdateStatusRead(**asdict(status))
