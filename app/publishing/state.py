"""Publishing state machine.

::

    draft ──► approved ──► queued ──► uploading ──► processing ──► published
      │          │  ▲         │          │  │            │
      │          │  └─ (revoke to draft)  │  │            ├──► failed
      ▼          ▼            ▼           │  ├──► failed  └──► unknown
   cancelled  cancelled   cancelled       │  └──► unknown
                                          └──► published
    failed ──► queued     (retry: only when the last attempt definitively failed)
    failed ──► cancelled
    unknown ──► published | failed   (only through reconciliation)

``published`` and ``cancelled`` are terminal. ``unknown`` means the upload may
or may not exist on the platform (e.g. the response was lost); it can never go
straight back to ``queued``, so a retry cannot create a duplicate post.
"""

from __future__ import annotations

from enum import StrEnum

from app.core.exceptions import InvalidStateTransitionError


class PostStatus(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    QUEUED = "queued"
    UPLOADING = "uploading"
    PROCESSING = "processing"
    PUBLISHED = "published"
    FAILED = "failed"
    UNKNOWN = "unknown"
    CANCELLED = "cancelled"


S = PostStatus

TRANSITIONS: dict[PostStatus, frozenset[PostStatus]] = {
    S.DRAFT: frozenset({S.APPROVED, S.CANCELLED}),
    S.APPROVED: frozenset({S.QUEUED, S.DRAFT, S.CANCELLED}),
    S.QUEUED: frozenset({S.UPLOADING, S.CANCELLED}),
    S.UPLOADING: frozenset({S.PROCESSING, S.PUBLISHED, S.FAILED, S.UNKNOWN}),
    S.PROCESSING: frozenset({S.PUBLISHED, S.FAILED, S.UNKNOWN}),
    S.FAILED: frozenset({S.QUEUED, S.CANCELLED}),
    S.UNKNOWN: frozenset({S.PUBLISHED, S.FAILED}),
    S.PUBLISHED: frozenset(),
    S.CANCELLED: frozenset(),
}

TERMINAL = frozenset({S.PUBLISHED, S.CANCELLED})


def can_transition(current: PostStatus, new: PostStatus) -> bool:
    return new in TRANSITIONS[current]


def require_transition(current: PostStatus | str, new: PostStatus | str) -> PostStatus:
    cur, nxt = PostStatus(current), PostStatus(new)
    if not can_transition(cur, nxt):
        allowed = ", ".join(sorted(s.value for s in TRANSITIONS[cur])) or "none (terminal)"
        raise InvalidStateTransitionError(
            f"Cannot move a post from '{cur.value}' to '{nxt.value}'. Allowed: {allowed}.",
            details={"from": cur.value, "to": nxt.value},
        )
    return nxt
