from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, Query, status

from app.api.deps import ContentPostServiceDep
from app.schemas.engagement import ContentPostCreate, ContentPostDetail, ContentPostList
from app.services.listing import SortOrder

router = APIRouter(prefix="/content-posts", tags=["posts"])


@router.get("", response_model=ContentPostList)
def list_content_posts(
    svc: ContentPostServiceDep,
    project_id: str | None = None,
    q: str | None = Query(default=None, max_length=100, description="Search in title and caption."),
    status: str | None = Query(default=None, max_length=16, description="Any of its platform posts has this status."),
    platform: str | None = Query(default=None, max_length=32, description="Targets this platform."),
    created_from: date | None = None,
    created_to: date | None = None,
    sort: Literal["created", "title"] | None = None,
    order: SortOrder = "desc",
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ContentPostList:
    """Posts (newest first by default) with the platforms they target and rolled-up metrics."""
    items, total = svc.list_posts(
        project_id=project_id,
        q=q,
        status=status,
        platform=platform,
        created_from=created_from,
        created_to=created_to,
        sort=sort,
        order=order,
        limit=limit,
        offset=offset,
    )
    return ContentPostList(items=items, total=total, limit=limit, offset=offset)


@router.post("", response_model=ContentPostDetail, status_code=status.HTTP_201_CREATED)
def create_content_post(body: ContentPostCreate, svc: ContentPostServiceDep) -> ContentPostDetail:
    """Create a post with one draft platform post per target. Nothing is published."""
    content = svc.create(body)
    return svc.detail(content.id)


@router.get("/{content_post_id}", response_model=ContentPostDetail)
def get_content_post(content_post_id: str, svc: ContentPostServiceDep) -> ContentPostDetail:
    return svc.detail(content_post_id)
