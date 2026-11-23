from __future__ import annotations

from fastapi import APIRouter, Query, status

from app.api.deps import ContentPostServiceDep
from app.schemas.engagement import ContentPostCreate, ContentPostDetail, ContentPostList

router = APIRouter(prefix="/content-posts", tags=["posts"])


@router.get("", response_model=ContentPostList)
def list_content_posts(
    svc: ContentPostServiceDep,
    project_id: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ContentPostList:
    """Posts, newest first, each with the platforms it targets and rolled-up metrics."""
    items, total = svc.list_posts(project_id=project_id, limit=limit, offset=offset)
    return ContentPostList(items=items, total=total)


@router.post("", response_model=ContentPostDetail, status_code=status.HTTP_201_CREATED)
def create_content_post(body: ContentPostCreate, svc: ContentPostServiceDep) -> ContentPostDetail:
    """Create a post with one draft platform post per target. Nothing is published."""
    content = svc.create(body)
    return svc.detail(content.id)


@router.get("/{content_post_id}", response_model=ContentPostDetail)
def get_content_post(content_post_id: str, svc: ContentPostServiceDep) -> ContentPostDetail:
    return svc.detail(content_post_id)
