"""Comments, interactions and analytics for *published* platform posts.

Everything here goes through the platform adapter contract. Operations the adapter
cannot really perform raise :class:`UnsupportedOperationError` *before* anything is
sent, so the UI can say exactly why. Nothing is simulated: with the shipped adapters
(none of which implement engagement yet) a sync reports "not implemented" and no
comments or metrics appear.

Every outward interaction that was actually attempted is written to
``engagement_actions`` (audit trail), whether it succeeded or not.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import AppConfig
from app.core.exceptions import (
    AppError,
    ConflictError,
    NotFoundError,
    PlatformError,
    UnsupportedOperationError,
    ValidationFailedError,
)
from app.core.security import redact
from app.database.base import utcnow
from app.models import Comment, EngagementAction, MetricSnapshot, Post
from app.publishing.state import PostStatus
from platforms.base import Capability, CapabilityState, Credentials, PlatformAdapter, RemoteComment

log = logging.getLogger(__name__)

MAX_REPLY_LENGTH = 2000
MAX_COMMENT_PAGES = 20

AdapterFactory = Callable[[str, dict[str, Any] | None], PlatformAdapter]
CredentialsResolver = Callable[[Post], Credentials]


@dataclass
class PartReport:
    """Outcome of one part of a sync (comments or analytics)."""

    #: ok | unsupported | error | skipped
    status: str
    count: int = 0
    message: str | None = None


@dataclass
class SyncReport:
    post_id: str
    comments: PartReport
    analytics: PartReport
    synced_at: datetime


def default_credentials(post: Post) -> Credentials:
    """Placeholder until OAuth is implemented: carries identity, no tokens.

    Real adapters will need a resolver backed by ``CredentialVault``; swap it in by
    passing ``credentials_for`` to :class:`EngagementService`.
    """
    return Credentials(platform=post.platform, account_id=post.account_id)


class EngagementService:
    def __init__(
        self,
        session: Session,
        config: AppConfig | None = None,
        *,
        adapter_factory: AdapterFactory | None = None,
        credentials_for: CredentialsResolver = default_credentials,
    ) -> None:
        self.session = session
        self.config = config
        self._factory = adapter_factory
        self._credentials_for = credentials_for

    # -- helpers ---------------------------------------------------------------

    def adapter_for(self, platform: str) -> PlatformAdapter:
        from platforms.registry import create_adapter

        cfg = self.config.platforms.platforms.get(platform) if self.config else None
        factory = self._factory or create_adapter
        return factory(platform, cfg)

    def get_post(self, post_id: str) -> Post:
        post = self.session.get(Post, post_id)
        if post is None:
            raise NotFoundError(f"Post '{post_id}' not found.")
        return post

    def _published(self, post_id: str) -> tuple[Post, str]:
        post = self.get_post(post_id)
        if post.status != PostStatus.PUBLISHED or not post.external_post_id:
            raise ConflictError(
                "Comments and analytics exist only for published posts "
                f"(this post is '{post.status}' and has no platform post id)."
            )
        return post, post.external_post_id

    def capabilities(self, post: Post) -> dict[str, str]:
        try:
            return self.adapter_for(post.platform).capability_map()
        except NotFoundError:
            return {c.value: CapabilityState.UNAVAILABLE.value for c in Capability}

    def get_comment(self, post_id: str, comment_id: str) -> Comment:
        comment = self.session.get(Comment, comment_id)
        if comment is None or comment.post_id != post_id:
            raise NotFoundError(f"Comment '{comment_id}' not found on this post.")
        return comment

    # -- reads -------------------------------------------------------------------

    def list_comments(
        self, post_id: str, *, limit: int = 100, offset: int = 0, include_hidden: bool = True
    ) -> tuple[list[Comment], int]:
        self.get_post(post_id)
        q = select(Comment).where(Comment.post_id == post_id)
        if not include_hidden:
            q = q.where(Comment.hidden.is_(False))
        total = self.session.scalar(select(func.count()).select_from(q.subquery())) or 0
        rows = self.session.scalars(
            q.order_by(Comment.posted_at.desc().nulls_last(), Comment.fetched_at.desc()).limit(limit).offset(offset)
        )
        return list(rows), int(total)

    def snapshots(self, post_id: str, limit: int = 200) -> list[MetricSnapshot]:
        rows = self.session.scalars(
            select(MetricSnapshot)
            .where(MetricSnapshot.post_id == post_id)
            .order_by(MetricSnapshot.collected_at.desc())
            .limit(limit)
        )
        return list(reversed(list(rows)))

    def actions(self, post_id: str, limit: int = 100) -> list[EngagementAction]:
        return list(
            self.session.scalars(
                select(EngagementAction)
                .where(EngagementAction.post_id == post_id)
                .order_by(EngagementAction.created_at.desc())
                .limit(limit)
            )
        )

    # -- sync --------------------------------------------------------------------

    def sync(self, post_id: str) -> SyncReport:
        """Pull comments and analytics from the platform. Each part reports independently."""
        post, external_id = self._published(post_id)
        adapter = self.adapter_for(post.platform)
        creds = self._credentials_for(post)
        comments = self._sync_comments(post, adapter, creds, external_id)
        analytics = self._sync_analytics(post, adapter, creds, external_id)
        return SyncReport(post_id=post.id, comments=comments, analytics=analytics, synced_at=utcnow())

    def _guarded(self, fn: Callable[[], PartReport]) -> PartReport:
        try:
            return fn()
        except UnsupportedOperationError as exc:
            return PartReport("unsupported", message=exc.message)
        except AppError as exc:
            return PartReport("error", message=redact(exc.message))
        except Exception as exc:
            log.exception("Platform sync failed")
            return PartReport("error", message=redact(f"{type(exc).__name__}: {exc}")[:500])

    def _sync_comments(self, post: Post, adapter: PlatformAdapter, creds: Credentials, external_id: str) -> PartReport:
        def run() -> PartReport:
            adapter.require(Capability.LIST_COMMENTS)
            seen: set[str] = set()
            cursor: str | None = None
            complete = False
            for _ in range(MAX_COMMENT_PAGES):
                page = adapter.list_comments(creds, external_id, cursor=cursor)
                for remote in page.comments:
                    self._upsert_comment(post, remote)
                    seen.add(remote.external_id)
                cursor = page.next_cursor
                if not cursor:
                    complete = True
                    break
            if complete:
                # Only a complete listing proves a comment is gone.
                for row in self.session.scalars(select(Comment).where(Comment.post_id == post.id)):
                    row.removed_remotely = row.external_id not in seen and not row.is_own
            self.session.commit()
            msg = None if complete else f"Stopped after {MAX_COMMENT_PAGES} pages; more comments exist."
            return PartReport("ok", count=len(seen), message=msg)

        report = self._guarded(run)
        if report.status == "error":
            self.session.rollback()
        return report

    def _upsert_comment(self, post: Post, remote: RemoteComment) -> None:
        row = self.session.scalar(
            select(Comment).where(Comment.post_id == post.id, Comment.external_id == remote.external_id)
        )
        if row is None:
            row = Comment(post_id=post.id, external_id=remote.external_id, text=remote.text)
            row.liked_by_me = False
            self.session.add(row)
        row.text = remote.text
        row.parent_external_id = remote.parent_external_id
        row.author_name = remote.author_name
        row.author_external_id = remote.author_external_id
        row.like_count = remote.like_count
        row.reply_count = remote.reply_count
        row.posted_at = remote.posted_at
        row.is_own = remote.is_own
        row.hidden = remote.hidden
        row.removed_remotely = False
        row.fetched_at = utcnow()

    def _sync_analytics(self, post: Post, adapter: PlatformAdapter, creds: Credentials, external_id: str) -> PartReport:
        def run() -> PartReport:
            adapter.require(Capability.ANALYTICS)
            result = adapter.get_analytics(creds, external_id)
            self.session.add(MetricSnapshot(post_id=post.id, collected_at=result.collected_at, metrics=result.metrics))
            post.analytics = {"collected_at": result.collected_at.isoformat(), "metrics": dict(result.metrics)}
            self.session.commit()
            return PartReport("ok", count=len(result.metrics))

        report = self._guarded(run)
        if report.status == "error":
            self.session.rollback()
        return report

    # -- interactions --------------------------------------------------------------

    def _record(
        self,
        post: Post,
        action: str,
        outcome: str,
        *,
        comment: str | None = None,
        detail: str | None = None,
        error: str | None = None,
    ) -> None:
        self.session.add(
            EngagementAction(
                post_id=post.id,
                comment_external_id=comment,
                action=action,
                outcome=outcome,
                detail=(detail or "")[:2000] or None,
                error=redact(error)[:2000] if error else None,
            )
        )

    def _perform(
        self,
        post: Post,
        capability: Capability,
        action: str,
        comment: Comment | None,
        detail: str | None,
        call: Callable[[PlatformAdapter, Credentials, str], Any],
    ) -> Any:
        post, external_id = self._published(post.id)
        adapter = self.adapter_for(post.platform)
        adapter.require(capability)  # raises before anything is sent
        creds = self._credentials_for(post)
        ext_comment = comment.external_id if comment else None
        try:
            result = call(adapter, creds, external_id)
        except Exception as exc:
            self.session.rollback()
            self._record(post, action, "failed", comment=ext_comment, detail=detail, error=str(exc))
            self.session.commit()
            if isinstance(exc, AppError):
                raise
            log.exception("Platform call failed: %s", action)
            raise PlatformError(f"{post.platform}: {action} failed: {redact(str(exc))[:300]}") from exc
        self._record(post, action, "succeeded", comment=ext_comment, detail=detail)
        return result

    def reply(self, post_id: str, comment_id: str, text: str) -> Comment:
        text = text.strip()
        if not text or len(text) > MAX_REPLY_LENGTH:
            raise ValidationFailedError(f"A reply must be 1-{MAX_REPLY_LENGTH} characters.")
        post = self.get_post(post_id)
        parent = self.get_comment(post_id, comment_id)
        remote: RemoteComment = self._perform(
            post,
            Capability.REPLY_COMMENT,
            "reply",
            parent,
            text,
            lambda a, c, ext: a.reply_to_comment(c, ext, parent.external_id, text),
        )
        remote.is_own = True
        remote.parent_external_id = remote.parent_external_id or parent.external_id
        self._upsert_comment(post, remote)
        parent.reply_count += 1
        self.session.commit()
        return self.session.scalar(
            select(Comment).where(Comment.post_id == post.id, Comment.external_id == remote.external_id)
        )  # type: ignore[return-value]

    def like_comment(self, post_id: str, comment_id: str, *, like: bool = True) -> Comment:
        post = self.get_post(post_id)
        comment = self.get_comment(post_id, comment_id)
        self._perform(
            post,
            Capability.LIKE_COMMENT,
            "like_comment" if like else "unlike_comment",
            comment,
            None,
            lambda a, c, ext: a.like_comment(c, ext, comment.external_id, like=like),
        )
        comment.liked_by_me = like
        self.session.commit()
        return comment

    def set_hidden(self, post_id: str, comment_id: str, *, hidden: bool) -> Comment:
        post = self.get_post(post_id)
        comment = self.get_comment(post_id, comment_id)
        self._perform(
            post,
            Capability.HIDE_COMMENT,
            "hide_comment" if hidden else "unhide_comment",
            comment,
            None,
            lambda a, c, ext: a.set_comment_hidden(c, ext, comment.external_id, hidden=hidden),
        )
        comment.hidden = hidden
        self.session.commit()
        return comment

    def delete_comment(self, post_id: str, comment_id: str) -> None:
        post = self.get_post(post_id)
        comment = self.get_comment(post_id, comment_id)
        self._perform(
            post,
            Capability.DELETE_COMMENT,
            "delete_comment",
            comment,
            None,
            lambda a, c, ext: a.delete_comment(c, ext, comment.external_id),
        )
        self.session.delete(comment)
        self.session.commit()

    def like_post(self, post_id: str, *, like: bool = True) -> None:
        post = self.get_post(post_id)
        self._perform(
            post,
            Capability.LIKE_POST,
            "like_post" if like else "unlike_post",
            None,
            None,
            lambda a, c, ext: a.like_post(c, ext, like=like),
        )
        self.session.commit()
