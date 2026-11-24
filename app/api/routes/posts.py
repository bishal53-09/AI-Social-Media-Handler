from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Query

from app.api.deps import ConfigDep, EngagementServiceDep, PostServiceDep, SessionDep
from app.models import Project
from app.schemas.engagement import (
    CommentList,
    CommentRead,
    HideRequest,
    LikeRequest,
    PartReportRead,
    ReplyRequest,
    SyncReportRead,
)
from app.schemas.post import PostList, PostRead
from app.services.listing import SortOrder

router = APIRouter(prefix="/posts", tags=["publishing"])


@router.get("", response_model=PostList)
def list_posts(
    svc: PostServiceDep,
    project_id: str | None = None,
    status: str | None = Query(default=None, max_length=16),
    platform: str | None = Query(default=None, max_length=32),
    sort: Literal["created", "status", "platform"] | None = None,
    order: SortOrder = "desc",
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> PostList:
    """Platform posts (one per platform). The user-facing view is ``/content-posts``."""
    items, total = svc.list_posts(
        project_id=project_id, status=status, platform=platform, sort=sort, order=order, limit=limit, offset=offset
    )
    return PostList(items=[PostRead.model_validate(p) for p in items], total=total, limit=limit, offset=offset)


@router.get("/{post_id}/comments", response_model=CommentList)
def list_comments(
    post_id: str,
    svc: EngagementServiceDep,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    include_hidden: bool = True,
) -> CommentList:
    """Comments last synced from the platform (plus our own replies). Empty until a sync succeeds."""
    rows, total = svc.list_comments(post_id, limit=limit, offset=offset, include_hidden=include_hidden)
    return CommentList(items=[CommentRead.model_validate(r) for r in rows], total=total)


@router.post("/{post_id}/sync", response_model=SyncReportRead)
def sync_post(post_id: str, svc: EngagementServiceDep) -> SyncReportRead:
    """Pull comments and analytics from the platform. Parts the adapter cannot do report why."""
    report = svc.sync(post_id)
    return SyncReportRead(
        post_id=report.post_id,
        comments=PartReportRead(**vars(report.comments)),
        analytics=PartReportRead(**vars(report.analytics)),
        synced_at=report.synced_at,
    )


@router.post("/{post_id}/comments/{comment_id}/reply", response_model=CommentRead, status_code=201)
def reply_to_comment(post_id: str, comment_id: str, body: ReplyRequest, svc: EngagementServiceDep) -> CommentRead:
    return CommentRead.model_validate(svc.reply(post_id, comment_id, body.text))


@router.post("/{post_id}/comments/{comment_id}/like", response_model=CommentRead)
def like_comment(
    post_id: str, comment_id: str, svc: EngagementServiceDep, body: LikeRequest | None = None
) -> CommentRead:
    return CommentRead.model_validate(svc.like_comment(post_id, comment_id, like=body.like if body else True))


@router.post("/{post_id}/comments/{comment_id}/hide", response_model=CommentRead)
def hide_comment(
    post_id: str, comment_id: str, svc: EngagementServiceDep, body: HideRequest | None = None
) -> CommentRead:
    return CommentRead.model_validate(svc.set_hidden(post_id, comment_id, hidden=body.hidden if body else True))


@router.delete("/{post_id}/comments/{comment_id}", status_code=204)
def delete_comment(post_id: str, comment_id: str, svc: EngagementServiceDep) -> None:
    svc.delete_comment(post_id, comment_id)


@router.post("/{post_id}/like", status_code=204)
def like_post(post_id: str, svc: EngagementServiceDep, body: LikeRequest | None = None) -> None:
    svc.like_post(post_id, like=body.like if body else True)


@router.post("/{post_id}/publish", response_model=PostRead)
def publish_post(post_id: str, svc: PostServiceDep, session: SessionDep, config: ConfigDep) -> PostRead:
    """Publish an approved, queued post through its platform's browser session (experimental)."""
    from app.core.paths import safe_join
    from platforms.registry import create_adapter

    post = svc.get(post_id)
    project = session.get(Project, post.project_id)
    adapter = create_adapter(post.platform, config.platforms.platforms.get(post.platform))
    media = safe_join(Path(project.path), post.output_file)  # type: ignore[union-attr]
    return PostRead.model_validate(svc.publish_now(post_id, adapter, media))
