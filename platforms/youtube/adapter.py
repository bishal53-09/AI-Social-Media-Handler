"""YouTube adapter: drives youtube.com / YouTube Studio through the user's logged-in browser profile.

All capabilities are experimental (see ``platforms.browser``). Posts are identified by their
watch URL. Google may refuse sign-in inside automated browsers; if so, sign in with the
real Chrome profile instead (``BROWSER_PROFILE_DIR`` points at a Chrome user-data dir).
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import ClassVar

from app.core.exceptions import PlatformError
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


class YouTubeAdapter(BrowserAdapter):
    name = "youtube"
    display_name = "YouTube"
    docs_url = "https://studio.youtube.com/"
    login_url = "https://studio.youtube.com/"
    logged_out_selector = 'a[href*="accounts.google.com/ServiceLogin"], ytd-button-renderer a[aria-label="Sign in"]'
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
        "Driven through your logged-in browser session (no API keys). Analytics are the public view and "
        "like counts on the watch page. Experimental: YouTube's official Data API would be more reliable "
        "for this platform, and automation may breach YouTube's terms."
    )
    default_limits: ClassVar[dict[str, MediaLimits]] = {
        "video": MediaLimits(
            max_duration_seconds=43200,
            min_duration_seconds=1,
            aspect_ratios=("16:9", "9:16", "1:1", "4:3"),
            max_file_size_mb=262144,
            containers=("mp4", "mov", "mkv", "webm"),
        ),
        # Shorts use this same adapter with Shorts-specific limits/metadata.
        "shorts": MediaLimits(
            max_duration_seconds=180,
            min_duration_seconds=1,
            aspect_ratios=("9:16", "1:1"),
            max_file_size_mb=262144,
            containers=("mp4", "mov"),
        ),
    }

    def publish(self, credentials: Credentials, request: PublishRequest) -> PublishResult:
        title, _, rest = request.caption.partition("\n")
        description = " ".join([rest.strip(), *(f"#{h.lstrip('#')}" for h in request.hashtags)]).strip()
        with self.session("https://studio.youtube.com/") as page:
            page.goto("https://www.youtube.com/upload")
            page.locator('input[type="file"]').first.set_input_files(str(request.media_path))
            boxes = page.locator("#textbox")
            boxes.first.wait_for(timeout=PUBLISH_TIMEOUT_MS)
            boxes.first.fill(title[:100] or request.media_path.stem)
            if description:
                boxes.nth(1).fill(description)
            page.get_by_role("radio", name="No, it's not made for kids").check()
            for _ in range(3):  # details → elements → checks → visibility
                page.get_by_role("button", name="Next").click()
                pause(page)
            page.get_by_role("radio", name="Public").check()
            link = page.locator('a[href*="youtu.be/"], a[href*="/shorts/"], a[href*="watch?v="]').first
            link.wait_for(timeout=PUBLISH_TIMEOUT_MS)
            href = link.get_attribute("href") or ""
            page.get_by_role("button", name="Publish").or_(page.get_by_role("button", name="Save")).click()
            page.get_by_text("Video published").or_(page.get_by_text("Video uploaded")).wait_for(
                timeout=PUBLISH_TIMEOUT_MS
            )
        m = re.search(r"(?:youtu\.be/|v=|/shorts/)([\w-]{11})", href)
        if not m:
            return PublishResult(status="processing")  # published, but the link was unreadable: reconcile
        url = f"https://www.youtube.com/watch?v={m.group(1)}"
        return PublishResult(status="published", external_post_id=url, external_url=url)

    def get_analytics(self, credentials: Credentials, external_post_id: str) -> Analytics:
        metrics: dict[str, float | int] = {}
        with self.session(external_post_id) as page:
            views = page.locator("ytd-watch-info-text #view-count, #info-container #info span").first
            if views.count() and (n := parse_count(views.inner_text())) is not None:
                metrics["views"] = n
            likes = page.locator("like-button-view-model button").first
            if likes.count() and (n := parse_count(likes.get_attribute("aria-label"))) is not None:
                metrics["likes"] = n
        if not metrics:
            raise PlatformError("YouTube: no counts found on the watch page (layout may have changed).")
        return Analytics(collected_at=datetime.now(UTC), metrics=metrics)

    def list_comments(
        self, credentials: Credentials, external_post_id: str, *, cursor: str | None = None, limit: int = 50
    ) -> CommentPage:
        out: list[RemoteComment] = []
        with self.session(external_post_id) as page:
            page.mouse.wheel(0, 1500)  # comments load lazily
            threads = page.locator("ytd-comment-thread-renderer")
            threads.first.wait_for(timeout=15_000)
            for i in range(min(threads.count(), limit)):
                t = threads.nth(i)
                author = t.locator("#author-text").first.inner_text().strip()
                text = t.locator("#content-text").first.inner_text().strip()
                out.append(RemoteComment(external_id=f"{i}:{author}", text=text, author_name=author))
        return CommentPage(comments=out)

    def reply_to_comment(
        self, credentials: Credentials, external_post_id: str, parent_comment_id: str, text: str
    ) -> RemoteComment:
        idx = int(parent_comment_id.split(":", 1)[0])
        with self.session(external_post_id) as page:
            page.mouse.wheel(0, 1500)
            thread = page.locator("ytd-comment-thread-renderer").nth(idx)
            thread.get_by_role("button", name="Reply").first.click()
            pause(page)
            thread.locator("#contenteditable-root").last.fill(text)
            thread.locator("#submit-button button").last.click()
            pause(page, 1500, 2500)
        return RemoteComment(external_id=f"own:{datetime.now(UTC).timestamp()}", text=text, is_own=True)

    def like_post(self, credentials: Credentials, external_post_id: str, *, like: bool = True) -> None:
        with self.session(external_post_id) as page:
            btn = page.locator("like-button-view-model button").first
            if not btn.count():
                raise PlatformError("YouTube: could not find the like button (the page layout may have changed).")
            if (btn.get_attribute("aria-pressed") == "true") != like:
                btn.click()
