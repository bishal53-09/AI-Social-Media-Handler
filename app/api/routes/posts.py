from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import PostServiceDep
from app.schemas.post import PostList, PostRead

router = APIRouter(prefix="/posts", tags=["publishing"])


@router.get("", response_model=PostList)
def list_posts(
    svc: PostServiceDep,
    project_id: str | None = None,
    status: str | None = Query(default=None, max_length=16),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> PostList:
    """Read-only for now: publishing adapters are not implemented (docs/roadmap.md)."""
    items, total = svc.list_posts(project_id=project_id, status=status, limit=limit, offset=offset)
    return PostList(items=[PostRead.model_validate(p) for p in items], total=total)
