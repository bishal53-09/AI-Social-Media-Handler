"""TikTok adapter: drives tiktok.com / TikTok Studio through the user's logged-in browser profile.

All capabilities are experimental (see ``platforms.browser``). Posts are identified by their
URL. Needs ``handle`` (without ``@``) under ``platforms.tiktok`` in config/platforms.yaml.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, ClassVar

from app.core.exceptions import PlatformError, ValidationFailedError
from platforms.base import (
    Analytics,
    Capability,
    CommentPage,
    Credentials,
    MediaLimits,
    PublishRequest,
    PublishResult,
    RemoteComment,
)
from platforms.browser import PUBLISH_TIMEOUT_MS, BrowserAdapter, parse_count, pause

METRIC_SELECTORS = {
    "likes": '[data-e2e="like-count"]',
    "comments": '[data-e2e="comment-count"]',
    "saves": '[data-e2e="undefined-count"]',
    "shares": '[data-e2e="share-count"]',
}


class TikTokAdapter(BrowserAdapter):
    name = "tiktok"
    display_name = "TikTok"
    docs_url = "https://www.tiktok.com/"
    login_url = "https://www.tiktok.com/login"
    logged_out_selector = '[data-e2e="top-login-button"]'
    experimental_capabilities: ClassVar[frozenset[Capability]] = frozenset(
        {
            Capability.PUBLISH,
            Capability.ANALYTICS,
            Capability.LIST_COMMENTS,
            Capability.REPLY_COMMENT,
            Capability.LIKE_POST,
        }
    )
    engagement_notes: ClassVar[str] = (
        "Driven through your logged-in browser session (no API keys). Analytics are the public counts "
        "(likes, comments, saves, shares) on the video page. Experimental: selectors may break when tiktok.com "
        "changes, and automation may breach TikTok's terms."
    )
    default_limits: ClassVar[dict[str, MediaLimits]] = {
        "video": MediaLimits(
            max_duration_seconds=600,
            min_duration_seconds=3,
            aspect_ratios=("9:16", "1:1", "16:9"),
            max_file_size_mb=4096,
            containers=("mp4", "mov", "webm"),
        ),
    }

    def publish(self, credentials: Credentials, request: PublishRequest) -> PublishResult:
        handle = self.config.get("handle")
        if not handle:
            raise ValidationFailedError("Set `handle` under platforms.tiktok in config/platforms.yaml.")
        caption = " ".join([request.caption, *(f"#{h.lstrip('#')}" for h in request.hashtags)]).strip()
        with self.session("https://www.tiktok.com/") as page:
            before = self._latest_video_url(page, handle)
            page.goto("https://www.tiktok.com/tiktokstudio/upload")
            frame = page.frame_locator("iframe").first if page.locator("iframe").count() else page
            frame.locator('input[type="file"]').first.set_input_files(str(request.media_path))
            editor = frame.locator('div[contenteditable="true"]').first
            editor.wait_for(timeout=PUBLISH_TIMEOUT_MS)
            editor.click()
            page.keyboard.press("Control+A")
            page.keyboard.type(caption, delay=30)
            pause(page)
            post = frame.get_by_role("button", name="Post", exact=True)
            post.wait_for(timeout=PUBLISH_TIMEOUT_MS)
            post.click()
            frame.get_by_text("Video published").or_(frame.get_by_text("Your video is being uploaded")).wait_for(
                timeout=PUBLISH_TIMEOUT_MS
            )
            url = self._latest_video_url(page, handle)
        if not url or url == before:
            return PublishResult(status="processing")  # submitted, but the URL is not visible yet: reconcile
        return PublishResult(status="published", external_post_id=url, external_url=url)

    def _latest_video_url(self, page: Any, handle: str) -> str | None:
        page.goto(f"https://www.tiktok.com/@{handle}")
        link = page.locator('[data-e2e="user-post-item"] a').first
        if not link.count():
            try:
                link.wait_for(timeout=15_000)
            except Exception:
                return None
        return link.get_attribute("href")

    def get_analytics(self, credentials: Credentials, external_post_id: str) -> Analytics:
        metrics: dict[str, float | int] = {}
        with self.session(external_post_id) as page:
            for key, selector in METRIC_SELECTORS.items():
                el = page.locator(selector).first
                if el.count() and (n := parse_count(el.inner_text())) is not None:
                    metrics[key] = n
        if not metrics:
            raise PlatformError("TikTok: no counts found on the video page (layout may have changed).")
        return Analytics(collected_at=datetime.now(UTC), metrics=metrics)

    def list_comments(
        self, credentials: Credentials, external_post_id: str, *, cursor: str | None = None, limit: int = 50
    ) -> CommentPage:
        out: list[RemoteComment] = []
        with self.session(external_post_id) as page:
            rows = page.locator('[data-e2e="comment-level-1"]')
            for i in range(min(rows.count(), limit)):
                row = rows.nth(i)
                author = row.locator('[data-e2e="comment-username-1"]').first.inner_text().strip()
                out.append(
                    RemoteComment(external_id=f"{i}:{author}", text=row.inner_text().strip(), author_name=author)
                )
        return CommentPage(comments=out)

    def reply_to_comment(
        self, credentials: Credentials, external_post_id: str, parent_comment_id: str, text: str
    ) -> RemoteComment:
        idx = int(parent_comment_id.split(":", 1)[0])
        with self.session(external_post_id) as page:
            page.locator('[data-e2e="comment-level-1"]').nth(idx).get_by_text("Reply", exact=True).click()
            pause(page)
            page.locator('[data-e2e="comment-input"] [contenteditable="true"]').first.fill(text)
            page.locator('[data-e2e="comment-post"]').click()
            pause(page, 1500, 2500)
        return RemoteComment(external_id=f"own:{datetime.now(UTC).timestamp()}", text=text, is_own=True)

    def like_post(self, credentials: Credentials, external_post_id: str, *, like: bool = True) -> None:
        with self.session(external_post_id) as page:
            btn = page.locator('[data-e2e="like-icon"]').first
            if not btn.count():
                raise PlatformError("TikTok: could not find the like control (the page layout may have changed).")
            if (btn.locator("xpath=ancestor::button[1]").get_attribute("aria-pressed") == "true") != like:
                btn.click()
