"""Post persistence and the publishing safety rules.

Safety rules enforced here (and tested):

* A post is only ever ``queued`` after human approval.
* An upload attempt is recorded (with an idempotency key) *before* any platform
  call, so a lost response leaves evidence instead of silence.
* After an ambiguous failure the post becomes ``unknown`` and must be
  *reconciled* against the platform before any retry.
* A retry is refused if the platform may already hold the post.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError, ValidationFailedError
from app.core.security import redact
from app.database.base import utcnow
from app.models import Post, PostAttempt, Project
from app.publishing.state import PostStatus, require_transition
from app.schemas.post import PostCreate
from app.services.listing import SortOrder, apply_sort

#: Columns the platform-post list can be sorted by (``?sort=``).
POST_SORT = {"created": Post.created_at, "status": Post.status, "platform": Post.platform}


class PostService:
    def __init__(self, session: Session) -> None:
        self.session = session

    # -- queries -------------------------------------------------------------

    def get(self, post_id: str) -> Post:
        post = self.session.get(Post, post_id)
        if post is None:
            raise NotFoundError(f"Post '{post_id}' not found.")
        return post

    def list_posts(
        self,
        *,
        project_id: str | None = None,
        status: str | None = None,
        platform: str | None = None,
        sort: str | None = None,
        order: SortOrder = "desc",
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Post], int]:
        q = select(Post)
        if project_id:
            q = q.where(Post.project_id == project_id)
        if status:
            q = q.where(Post.status == status)
        if platform:
            q = q.where(Post.platform == platform)
        total = self.session.scalar(select(func.count()).select_from(q.subquery())) or 0
        q = apply_sort(q, POST_SORT, sort, order, [Post.created_at.desc()], Post.id)
        return list(self.session.scalars(q.limit(limit).offset(offset))), int(total)

    def attempts(self, post_id: str) -> list[PostAttempt]:
        return list(
            self.session.scalars(
                select(PostAttempt).where(PostAttempt.post_id == post_id).order_by(PostAttempt.attempt)
            )
        )

    # -- transitions ---------------------------------------------------------

    def create_draft(self, data: PostCreate) -> Post:
        if self.session.get(Project, data.project_id) is None:
            raise NotFoundError(f"Project '{data.project_id}' not found.")
        files = data.media_files or [data.output_file]
        for f in files:
            if f.startswith(("/", "~")) or ".." in f.split("/"):
                raise ValidationFailedError("Media files must be paths relative to the project.")
        tags = [t.lstrip("#") for t in data.hashtags]
        fields = data.model_dump(exclude={"hashtags", "media_files", "output_file"})
        post = Post(**fields, output_file=files[0], media_files=files, hashtags=tags, status=PostStatus.DRAFT)
        self.session.add(post)
        self.session.commit()
        return post

    def _move(self, post: Post, new: PostStatus) -> None:
        post.status = require_transition(post.status, new).value

    def approve(self, post_id: str, approver: str) -> Post:
        if not approver.strip():
            raise ValidationFailedError("An approver name is required.")
        post = self.get(post_id)
        self._move(post, PostStatus.APPROVED)
        post.approved_by, post.approved_at = approver.strip(), utcnow()
        self.session.commit()
        return post

    def revoke_approval(self, post_id: str) -> Post:
        post = self.get(post_id)
        self._move(post, PostStatus.DRAFT)
        post.approved_by = post.approved_at = None
        self.session.commit()
        return post

    def cancel(self, post_id: str) -> Post:
        post = self.get(post_id)
        if post.external_post_id:
            raise ConflictError("A platform post already exists; it cannot be cancelled here.")
        self._move(post, PostStatus.CANCELLED)
        self.session.commit()
        return post

    def queue(self, post_id: str, *, now: datetime | None = None) -> Post:
        """approved → queued, or failed → queued (retry)."""
        post = self.get(post_id)
        if not post.approved_by or post.approved_at is None:
            raise ConflictError("Publishing requires explicit human approval first.")
        if post.status == PostStatus.FAILED:
            self._assert_safe_to_retry(post)
        self._move(post, PostStatus.QUEUED)
        post.error = None
        self.session.commit()
        return post

    def _assert_safe_to_retry(self, post: Post) -> None:
        if post.external_post_id:
            raise ConflictError("The platform already has this post; not retrying.")
        attempts = self.attempts(post.id)
        if attempts and attempts[-1].outcome != "failed":
            raise ConflictError(
                "The last upload attempt did not definitively fail. Reconcile with the "
                "platform before retrying to avoid a duplicate post."
            )

    # -- upload attempts -------------------------------------------------------

    def begin_attempt(self, post_id: str) -> PostAttempt:
        """queued → uploading, recording the attempt *before* contacting the platform."""
        post = self.get(post_id)
        if post.status == PostStatus.QUEUED:
            self._assert_safe_to_retry(post)
        self._move(post, PostStatus.UPLOADING)
        n = len(self.attempts(post.id)) + 1
        attempt = PostAttempt(post_id=post.id, attempt=n, idempotency_key=uuid.uuid4().hex, outcome="in_progress")
        self.session.add(attempt)
        self.session.commit()
        return attempt

    def record_upload_reference(self, attempt: PostAttempt, reference: str) -> None:
        """Persist a platform-side handle (upload/container id) as soon as it is known."""
        attempt.upload_reference = reference
        self.session.commit()

    def mark_processing(self, post_id: str) -> Post:
        post = self.get(post_id)
        self._move(post, PostStatus.PROCESSING)
        self.session.commit()
        return post

    def complete_attempt(
        self,
        post_id: str,
        attempt: PostAttempt,
        *,
        external_post_id: str,
        external_url: str | None = None,
    ) -> Post:
        if not external_post_id:
            raise ValidationFailedError("A published post must have an external post id.")
        post = self.get(post_id)
        self._move(post, PostStatus.PUBLISHED)
        now = utcnow()
        post.external_post_id, post.external_url, post.published_at = external_post_id, external_url, now
        post.error = None
        attempt.outcome, attempt.finished_at = "success", now
        self.session.commit()
        return post

    def fail_attempt(self, post_id: str, attempt: PostAttempt, error: str, *, definitive: bool) -> Post:
        """Record a failure.

        ``definitive=True``: the platform rejected the upload (safe to retry).
        ``definitive=False``: outcome unknown (timeout, lost response) → ``unknown``.
        """
        post = self.get(post_id)
        self._move(post, PostStatus.FAILED if definitive else PostStatus.UNKNOWN)
        attempt.outcome = "failed" if definitive else "unknown"
        attempt.finished_at = utcnow()
        attempt.error = post.error = redact(error)[:2000]
        self.session.commit()
        return post

    def reconcile(
        self,
        post_id: str,
        *,
        found: bool,
        external_post_id: str | None = None,
        external_url: str | None = None,
    ) -> Post:
        """Resolve an ``unknown`` post using what the platform reports."""
        post = self.get(post_id)
        if post.status != PostStatus.UNKNOWN:
            raise ConflictError("Only posts in 'unknown' state need reconciliation.")
        attempts = self.attempts(post.id)
        last = attempts[-1] if attempts else None
        if found:
            if not external_post_id:
                raise ValidationFailedError("external_post_id is required when the post was found.")
            self._move(post, PostStatus.PUBLISHED)
            post.external_post_id, post.external_url = external_post_id, external_url
            post.published_at = utcnow()
            post.error = None
            if last:
                last.outcome, last.finished_at = "success", utcnow()
        else:
            self._move(post, PostStatus.FAILED)
            post.error = "Reconciled: the platform has no matching post."
            if last:
                last.outcome, last.finished_at = "failed", utcnow()
        self.session.commit()
        return post
