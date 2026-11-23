"""The user-facing *post*: one piece of content, its platform posts, and rollups."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import AppConfig
from app.core.exceptions import NotFoundError, ValidationFailedError
from app.models import Comment, ContentPost, MediaAsset, Post, Project
from app.schemas.engagement import (
    AnalyticsOverview,
    ContentPostCreate,
    ContentPostDetail,
    ContentPostSummary,
    PlatformBreakdown,
    PlatformPostDetail,
    PlatformPostSummary,
    TopPost,
)
from app.schemas.post import PostAttemptRead, PostCreate
from app.services.engagement_service import EngagementService
from app.services.post_service import PostService
from platforms.base import ADDITIVE_METRICS
from platforms.registry import get_registry


def _latest_metrics(post: Post) -> tuple[dict[str, Any], datetime | None]:
    data = post.analytics or {}
    collected = data.get("collected_at")
    try:
        when = datetime.fromisoformat(collected) if collected else None
    except ValueError:
        when = None
    return dict(data.get("metrics") or {}), when


def _sum_additive(metric_dicts: list[dict[str, Any]]) -> dict[str, float | int]:
    totals: dict[str, float | int] = {}
    for m in metric_dicts:
        for key in ADDITIVE_METRICS:
            value = m.get(key)
            if isinstance(value, int | float) and not isinstance(value, bool):
                totals[key] = totals.get(key, 0) + value
    return totals


class ContentPostService:
    def __init__(self, session: Session, config: AppConfig | None = None, engagement: EngagementService | None = None):
        self.session = session
        self.config = config
        self.engagement = engagement or EngagementService(session, config)

    # -- create ---------------------------------------------------------------------

    def create(self, data: ContentPostCreate) -> ContentPost:
        if self.session.get(Project, data.project_id) is None:
            raise NotFoundError(f"Project '{data.project_id}' not found.")
        files = data.files
        self._check_media(data.project_id, files, explicit=bool(data.media_files))
        registry = get_registry()
        seen: set[tuple[str, str | None]] = set()
        for target in data.platforms:
            key = (target.platform, target.variant)
            if key in seen:
                raise ValidationFailedError(f"Platform '{target.platform}' is listed twice for this post.")
            seen.add(key)
            adapter_cls = registry.get(target.platform)
            if adapter_cls is None:
                raise ValidationFailedError(
                    f"Unknown platform '{target.platform}'.", details={"available": sorted(registry)}
                )
            cfg = (self.config.platforms.platforms.get(target.platform) if self.config else None) or {}
            variants = {*adapter_cls.default_limits, *(cfg.get("media") or {})}
            if target.variant is not None and target.variant not in variants:
                raise ValidationFailedError(
                    f"{adapter_cls.display_name} has no variant '{target.variant}'.",
                    details={"variants": sorted(variants)},
                )
            allowed = adapter_cls(cfg).limits_for(target.variant).max_files
            if len(files) > allowed:
                label = f"{adapter_cls.display_name}" + (f" {target.variant}" if target.variant else "")
                raise ValidationFailedError(
                    f"{label} accepts {allowed} media file{'s' if allowed != 1 else ''} per post; "
                    f"{len(files)} selected.",
                    details={"platform": target.platform, "variant": target.variant, "max_files": allowed},
                )
        tags = [t.lstrip("#") for t in data.hashtags]
        content = ContentPost(
            project_id=data.project_id,
            title=data.title,
            output_file=files[0],
            media_files=files,
            caption=data.caption,
            hashtags=tags,
        )
        self.session.add(content)
        self.session.flush()
        posts = PostService(self.session)
        try:
            for target in data.platforms:
                posts.create_draft(
                    PostCreate(
                        project_id=data.project_id,
                        content_post_id=content.id,
                        platform=target.platform,
                        variant=target.variant,
                        output_file=files[0],
                        media_files=files,
                        caption=data.caption,
                        hashtags=tags,
                        scheduled_at=data.scheduled_at,
                    )
                )
        except Exception:
            self.session.rollback()
            raise
        return content

    def _check_media(self, project_id: str, files: list[str], *, explicit: bool) -> None:
        for f in files:
            if f.startswith(("/", "~")) or ".." in f.split("/"):
                raise ValidationFailedError("Media files must be paths relative to the project.")
        if not explicit:  # legacy single ``output_file``: path rules only
            return
        found = {
            a.relative_path
            for a in self.session.scalars(
                select(MediaAsset).where(
                    MediaAsset.project_id == project_id,
                    MediaAsset.relative_path.in_(files),
                    MediaAsset.missing.is_(False),
                )
            )
        }
        unknown = [f for f in files if f not in found]
        if unknown:
            raise ValidationFailedError(
                "Some selected media is not in the project's media index. Rescan media and pick again.",
                details={"unknown": unknown},
            )

    # -- reads ----------------------------------------------------------------------

    def get(self, content_post_id: str) -> ContentPost:
        content = self.session.get(ContentPost, content_post_id)
        if content is None:
            raise NotFoundError(f"Post '{content_post_id}' not found.")
        return content

    def list_posts(
        self, *, project_id: str | None = None, limit: int = 50, offset: int = 0
    ) -> tuple[list[ContentPostSummary], int]:
        q = select(ContentPost)
        if project_id:
            q = q.where(ContentPost.project_id == project_id)
        total = self.session.scalar(select(func.count()).select_from(q.subquery())) or 0
        rows = list(self.session.scalars(q.order_by(ContentPost.created_at.desc()).limit(limit).offset(offset)))
        return self._summaries(rows), int(total)

    def _summaries(self, rows: list[ContentPost]) -> list[ContentPostSummary]:
        by_content = self._posts_for([c.id for c in rows])
        return [self._summary(c, by_content[c.id]) for c in rows]

    def _posts_for(self, content_ids: list[str]) -> dict[str, list[Post]]:
        out: dict[str, list[Post]] = defaultdict(list)
        if content_ids:
            for p in self.session.scalars(
                select(Post).where(Post.content_post_id.in_(content_ids)).order_by(Post.platform, Post.variant)
            ):
                out[p.content_post_id or ""].append(p)
        return out

    def _comment_counts(self, post_ids: list[str]) -> dict[str, int]:
        if not post_ids:
            return {}
        rows = self.session.execute(
            select(Comment.post_id, func.count())
            .where(Comment.post_id.in_(post_ids), Comment.removed_remotely.is_(False))
            .group_by(Comment.post_id)
        )
        return {pid: int(n) for pid, n in rows}

    def _platform_name(self, platform: str) -> str:
        cls = get_registry().get(platform)
        return cls.display_name if cls else platform

    def _post_summary(self, post: Post, counts: dict[str, int]) -> PlatformPostSummary:
        metrics, when = _latest_metrics(post)
        return PlatformPostSummary(
            id=post.id,
            platform=post.platform,
            platform_name=self._platform_name(post.platform),
            variant=post.variant,
            status=post.status,
            external_post_id=post.external_post_id,
            external_url=post.external_url,
            published_at=post.published_at,
            scheduled_at=post.scheduled_at,
            error=post.error,
            metrics=metrics,
            metrics_collected_at=when,
            comment_count=counts.get(post.id, 0),
        )

    def _summary(self, content: ContentPost, posts: list[Post]) -> ContentPostSummary:
        counts = self._comment_counts([p.id for p in posts])
        items = [self._post_summary(p, counts) for p in posts]
        return ContentPostSummary(
            id=content.id,
            project_id=content.project_id,
            title=content.title,
            output_file=content.output_file,
            media_files=list(content.media_files or ([content.output_file] if content.output_file else [])),
            caption=content.caption,
            hashtags=list(content.hashtags or []),
            created_at=content.created_at,
            platform_posts=items,
            totals=_sum_additive([i.metrics for i in items]),
            comment_total=sum(counts.values()),
        )

    def detail(self, content_post_id: str) -> ContentPostDetail:
        content = self.get(content_post_id)
        posts = self._posts_for([content.id])[content.id]
        base = self._summary(content, posts)
        counts = self._comment_counts([p.id for p in posts])
        post_service = PostService(self.session)
        details: list[PlatformPostDetail] = []
        for post in posts:
            summary = self._post_summary(post, counts)
            adapter_cls = get_registry().get(post.platform)
            details.append(
                PlatformPostDetail(
                    **summary.model_dump(),
                    caption=post.caption,
                    hashtags=list(post.hashtags or []),
                    approved_by=post.approved_by,
                    approved_at=post.approved_at,
                    attempts=[PostAttemptRead.model_validate(a) for a in post_service.attempts(post.id)],
                    capabilities=self.engagement.capabilities(post),
                    engagement_notes=adapter_cls.engagement_notes if adapter_cls else "",
                    snapshots=[
                        {"collected_at": s.collected_at, "metrics": s.metrics}  # type: ignore[misc]
                        for s in self.engagement.snapshots(post.id)
                    ],
                    actions=[
                        {  # type: ignore[misc]
                            "id": a.id,
                            "comment_external_id": a.comment_external_id,
                            "action": a.action,
                            "outcome": a.outcome,
                            "detail": a.detail,
                            "error": a.error,
                            "created_at": a.created_at,
                        }
                        for a in self.engagement.actions(post.id, limit=50)
                    ],
                )
            )
        return ContentPostDetail(**{**base.model_dump(), "platform_posts": details})

    # -- analytics ------------------------------------------------------------------

    def analytics_overview(self, project_id: str | None = None, top: int = 10) -> AnalyticsOverview:
        q = select(Post).where(Post.status == "published")
        if project_id:
            q = q.where(Post.project_id == project_id)
        posts = list(self.session.scalars(q))
        content_titles = {
            c.id: c.title
            for c in self.session.scalars(
                select(ContentPost).where(ContentPost.id.in_({p.content_post_id for p in posts if p.content_post_id}))
            )
        }
        with_data = [(p, _latest_metrics(p)) for p in posts if p.analytics]
        by_platform: dict[str, list[tuple[Post, dict[str, Any]]]] = defaultdict(list)
        published_counts: dict[str, int] = defaultdict(int)
        for p in posts:
            published_counts[p.platform] += 1
        for p, (metrics, _) in with_data:
            by_platform[p.platform].append((p, metrics))
        breakdown = [
            PlatformBreakdown(
                platform=name,
                platform_name=self._platform_name(name),
                published_posts=published_counts[name],
                posts_with_data=len(by_platform.get(name, [])),
                totals=_sum_additive([m for _, m in by_platform.get(name, [])]),
            )
            for name in sorted(published_counts)
        ]
        ranked = sorted(with_data, key=lambda t: float(t[1][0].get("views") or 0), reverse=True)[:top]
        collected = [when for _, (_, when) in with_data if when]
        return AnalyticsOverview(
            published_posts=len(posts),
            posts_with_data=len(with_data),
            totals=_sum_additive([m for _, (m, _) in with_data]),
            by_platform=breakdown,
            top_posts=[
                TopPost(
                    content_post_id=p.content_post_id,
                    title=content_titles.get(p.content_post_id or "", p.output_file),
                    platform=p.platform,
                    platform_post_id=p.id,
                    external_url=p.external_url,
                    metrics=m,
                )
                for p, (m, _) in ranked
            ],
            last_collected_at=max(collected) if collected else None,
        )
