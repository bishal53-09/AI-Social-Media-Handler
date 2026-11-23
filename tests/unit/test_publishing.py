from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, InvalidStateTransitionError, ValidationFailedError
from app.models import Post, Project
from app.publishing.state import TERMINAL, TRANSITIONS, PostStatus, can_transition, require_transition
from app.schemas.post import PostCreate
from app.services.post_service import PostService

S = PostStatus


# --- pure state machine -------------------------------------------------------


def test_every_status_has_a_transition_entry() -> None:
    assert set(TRANSITIONS) == set(PostStatus)
    assert {s.value for s in PostStatus} == {
        "draft",
        "approved",
        "queued",
        "uploading",
        "processing",
        "published",
        "failed",
        "unknown",
        "cancelled",
    }


def test_terminal_states_have_no_exits() -> None:
    assert {S.PUBLISHED, S.CANCELLED} == TERMINAL
    for s in TERMINAL:
        assert TRANSITIONS[s] == frozenset()


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (S.DRAFT, S.APPROVED),
        (S.APPROVED, S.QUEUED),
        (S.QUEUED, S.UPLOADING),
        (S.UPLOADING, S.PROCESSING),
        (S.PROCESSING, S.PUBLISHED),
        (S.UPLOADING, S.UNKNOWN),
        (S.UNKNOWN, S.PUBLISHED),
        (S.UNKNOWN, S.FAILED),
        (S.FAILED, S.QUEUED),
    ],
)
def test_allowed_transitions(a: PostStatus, b: PostStatus) -> None:
    assert can_transition(a, b)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (S.DRAFT, S.QUEUED),  # cannot skip approval
        (S.DRAFT, S.PUBLISHED),
        (S.APPROVED, S.UPLOADING),
        (S.QUEUED, S.PUBLISHED),
        (S.UNKNOWN, S.QUEUED),  # cannot retry blindly after an ambiguous failure
        (S.UNKNOWN, S.UPLOADING),
        (S.PUBLISHED, S.QUEUED),
        (S.PUBLISHED, S.FAILED),
        (S.CANCELLED, S.DRAFT),
        (S.FAILED, S.UPLOADING),
    ],
)
def test_forbidden_transitions(a: PostStatus, b: PostStatus) -> None:
    assert not can_transition(a, b)
    with pytest.raises(InvalidStateTransitionError):
        require_transition(a, b)


# --- service ---------------------------------------------------------------------


@pytest.fixture
def svc(session: Session) -> PostService:
    session.add(Project(id="p", name="P", path="/p"))
    session.commit()
    return PostService(session)


def draft(svc: PostService, **kw) -> Post:  # type: ignore[no-untyped-def]
    return svc.create_draft(PostCreate(project_id="p", platform="youtube", output_file="exports/approved/a.mp4", **kw))


def queued(svc: PostService) -> Post:
    p = draft(svc)
    svc.approve(p.id, "Bishal")
    return svc.queue(p.id)


def test_draft_defaults_and_hashtag_normalisation(svc: PostService) -> None:
    p = draft(svc, hashtags=["#travel", "osmo"], caption="hi")
    assert p.status == "draft" and p.hashtags == ["travel", "osmo"] and p.id.startswith("post_")
    assert p.external_post_id is None


def test_scheduled_time_must_be_timezone_aware() -> None:
    with pytest.raises(ValidationError):
        PostCreate(project_id="p", platform="x", output_file="a.mp4", scheduled_at=datetime(2026, 1, 1, 12, 0))
    ok = PostCreate(
        project_id="p", platform="x", output_file="a.mp4", scheduled_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    )
    assert ok.scheduled_at is not None


@pytest.mark.parametrize("bad", ["/etc/passwd", "../x.mp4", "~/x.mp4", "a/../../x"])
def test_output_file_must_be_project_relative(svc: PostService, bad: str) -> None:
    with pytest.raises(ValidationFailedError):
        svc.create_draft(PostCreate(project_id="p", platform="x", output_file=bad))


def test_publishing_requires_human_approval(svc: PostService) -> None:
    p = draft(svc)
    with pytest.raises(ConflictError, match="human approval"):
        svc.queue(p.id)
    with pytest.raises(ValidationFailedError):
        svc.approve(p.id, "  ")
    svc.approve(p.id, "Bishal")
    got = svc.get(p.id)
    assert got.approved_by == "Bishal" and got.approved_at is not None
    assert svc.queue(p.id).status == "queued"


def test_revoking_approval_clears_it(svc: PostService) -> None:
    p = draft(svc)
    svc.approve(p.id, "B")
    svc.revoke_approval(p.id)
    got = svc.get(p.id)
    assert got.status == "draft" and got.approved_by is None
    with pytest.raises(ConflictError, match="human approval"):
        svc.queue(p.id)


def test_happy_path_to_published(svc: PostService) -> None:
    p = queued(svc)
    attempt = svc.begin_attempt(p.id)
    assert attempt.attempt == 1 and attempt.idempotency_key and attempt.outcome == "in_progress"
    assert svc.get(p.id).status == "uploading"
    svc.record_upload_reference(attempt, "upload-session-123")
    svc.mark_processing(p.id)
    done = svc.complete_attempt(p.id, attempt, external_post_id="yt_abc", external_url="https://youtu.be/abc")
    assert done.status == "published" and done.external_post_id == "yt_abc"
    assert done.published_at is not None and done.published_at.tzinfo is not None
    assert svc.attempts(p.id)[0].outcome == "success"
    with pytest.raises(InvalidStateTransitionError):
        svc.queue(p.id)  # a published post can never be queued again


def test_published_post_requires_external_id(svc: PostService) -> None:
    p = queued(svc)
    a = svc.begin_attempt(p.id)
    with pytest.raises(ValidationFailedError):
        svc.complete_attempt(p.id, a, external_post_id="")


def test_definitive_failure_allows_a_safe_retry_with_attempt_history(svc: PostService) -> None:
    p = queued(svc)
    a1 = svc.begin_attempt(p.id)
    svc.fail_attempt(p.id, a1, "Platform rejected: invalid aspect ratio", definitive=True)
    assert svc.get(p.id).status == "failed"
    svc.queue(p.id)  # retry
    a2 = svc.begin_attempt(p.id)
    assert a2.attempt == 2 and a2.idempotency_key != a1.idempotency_key
    svc.complete_attempt(p.id, a2, external_post_id="id2")
    history = svc.attempts(p.id)
    assert [x.outcome for x in history] == ["failed", "success"]
    assert history[0].error and "aspect" in history[0].error


def test_lost_response_leads_to_unknown_and_blocks_blind_retry(svc: PostService) -> None:
    p = queued(svc)
    a = svc.begin_attempt(p.id)
    svc.record_upload_reference(a, "container-9")
    svc.fail_attempt(p.id, a, "timeout waiting for response", definitive=False)
    post = svc.get(p.id)
    assert post.status == "unknown"
    with pytest.raises(InvalidStateTransitionError):
        svc.queue(p.id)  # unknown → queued is not allowed
    assert svc.attempts(p.id)[0].upload_reference == "container-9"  # kept for reconciliation


def test_reconcile_found_publishes_without_a_second_upload(svc: PostService) -> None:
    p = queued(svc)
    a = svc.begin_attempt(p.id)
    svc.fail_attempt(p.id, a, "connection reset", definitive=False)
    done = svc.reconcile(p.id, found=True, external_post_id="remote-1", external_url="https://x/1")
    assert done.status == "published" and done.external_post_id == "remote-1"
    assert len(svc.attempts(p.id)) == 1 and svc.attempts(p.id)[0].outcome == "success"
    with pytest.raises(InvalidStateTransitionError):
        svc.begin_attempt(p.id)


def test_reconcile_not_found_then_retry_is_allowed(svc: PostService) -> None:
    p = queued(svc)
    a = svc.begin_attempt(p.id)
    svc.fail_attempt(p.id, a, "connection reset", definitive=False)
    failed = svc.reconcile(p.id, found=False)
    assert failed.status == "failed" and "no matching post" in (failed.error or "")
    assert svc.attempts(p.id)[0].outcome == "failed"
    svc.queue(p.id)
    assert svc.begin_attempt(p.id).attempt == 2


def test_reconcile_input_checks(svc: PostService) -> None:
    p = queued(svc)
    with pytest.raises(ConflictError):
        svc.reconcile(p.id, found=False)  # not unknown
    a = svc.begin_attempt(p.id)
    svc.fail_attempt(p.id, a, "x", definitive=False)
    with pytest.raises(ValidationFailedError):
        svc.reconcile(p.id, found=True)  # found but no external id


def test_retry_is_refused_if_platform_may_already_have_the_post(svc: PostService, session: Session) -> None:
    p = queued(svc)
    a = svc.begin_attempt(p.id)
    svc.fail_attempt(p.id, a, "x", definitive=True)
    post = svc.get(p.id)
    post.external_post_id = "already-there"
    session.commit()
    with pytest.raises(ConflictError, match="already has this post"):
        svc.queue(p.id)


def test_cancel_rules(svc: PostService) -> None:
    p = draft(svc)
    assert svc.cancel(p.id).status == "cancelled"
    with pytest.raises(InvalidStateTransitionError):
        svc.approve(p.id, "B")
    q = queued(svc)
    a = svc.begin_attempt(q.id)
    with pytest.raises(InvalidStateTransitionError):
        svc.cancel(q.id)  # cannot cancel mid-upload
    svc.complete_attempt(q.id, a, external_post_id="z")
    with pytest.raises(ConflictError):
        svc.cancel(q.id)  # nor after publishing


def test_error_text_is_redacted(svc: PostService) -> None:
    p = queued(svc)
    a = svc.begin_attempt(p.id)
    svc.fail_attempt(p.id, a, "401 Bearer abcdefghijklmnop rejected", definitive=True)
    assert "abcdefghijklmnop" not in (svc.get(p.id).error or "")
