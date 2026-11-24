"""Instagram adapter: drives instagram.com through the user's logged-in browser profile.

All capabilities are experimental (see ``platforms.browser``). Posts are identified by
their URL. Needs ``handle`` under ``platforms.instagram`` in config/platforms.yaml to find
a freshly published post.
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
    RemotePostStatus,
)
from platforms.browser import PUBLISH_TIMEOUT_MS, BrowserAdapter, parse_count, pause

POST_LINK = 'a[href*="/reel/"], a[href*="/p/"]'


class InstagramAdapter(BrowserAdapter):
    name = "instagram"
    display_name = "Instagram"
    docs_url = "https://www.instagram.com/"
    login_url = "https://www.instagram.com/accounts/login/"
    logged_out_selector = 'input[name="username"]'
    experimental_capabilities: ClassVar[frozenset[Capability]] = frozenset(
        {
            Capability.PUBLISH,
            Capability.ANALYTICS,
            Capability.LIST_COMMENTS,
            Capability.REPLY_COMMENT,
            Capability.LIKE_POST,
            Capability.LIKE_COMMENT,
        }
    )
    engagement_notes: ClassVar[str] = (
        "Driven through your logged-in browser session (no API keys). Analytics are the public counts "
        "(likes, comments, plays) visible on the post page; reach/impressions are not available. "
        "Experimental: selectors may break when instagram.com changes, and automation may breach "
        "Instagram's terms."
    )
    default_limits: ClassVar[dict[str, MediaLimits]] = {
        "reels": MediaLimits(
            max_duration_seconds=900,
            min_duration_seconds=3,
            aspect_ratios=("9:16",),
            max_file_size_mb=1024,
            containers=("mp4", "mov"),
        ),
        "carousel": MediaLimits(
            max_file_size_mb=1024,
            containers=("mp4", "mov", "jpg", "jpeg", "png"),
            max_files=10,
        ),
    }

    # -- publish ---------------------------------------------------------------

    def publish(self, credentials: Credentials, request: PublishRequest) -> PublishResult:
        handle = self.config.get("handle")
        if not handle:
            raise ValidationFailedError("Set `handle` under platforms.instagram in config/platforms.yaml.")
        caption = " ".join([request.caption, *(f"#{h.lstrip('#')}" for h in request.hashtags)]).strip()
        with self.session("https://www.instagram.com/") as page:
            before = self._latest_post_url(page, handle)
            page.goto("https://www.instagram.com/")
            page.get_by_role("link", name="New post").first.click()
            pause(page)
            page.get_by_role("link", name="Post").first.click()
            with page.expect_file_chooser() as chooser:
                page.get_by_role("button", name="Select from computer").click()
            chooser.value.set_files(str(request.media_path))
            page.get_by_role("button", name="Next").wait_for(timeout=PUBLISH_TIMEOUT_MS)
            for _ in range(2):  # crop, then edit
                page.get_by_role("button", name="Next").click()
                pause(page)
            page.get_by_role("textbox", name="Write a caption").fill(caption)
            pause(page)
            page.get_by_role("button", name="Share").click()
            page.get_by_text("Your reel has been shared").or_(page.get_by_text("Your post has been shared")).wait_for(
                timeout=PUBLISH_TIMEOUT_MS
            )
            url = self._latest_post_url(page, handle)
        if not url or url == before:
            return PublishResult(status="processing")  # shared, but we could not find the URL: reconcile
        return PublishResult(status="published", external_post_id=url, external_url=url)

    def _latest_post_url(self, page: Any, handle: str) -> str | None:
        page.goto(f"https://www.instagram.com/{handle}/")
        link = page.locator(POST_LINK).first
        link.wait_for(timeout=15_000)
        href = link.get_attribute("href")
        return f"https://www.instagram.com{href}" if href and href.startswith("/") else href

    def get_post_status(self, credentials: Credentials, **kw: Any) -> RemotePostStatus:
        url = kw.get("external_post_id")
        if not url:
            return RemotePostStatus(found=False)
        with self.session(url) as page:
            found = page.locator("article, main").count() > 0 and not page.get_by_text("isn't available").count()
        return RemotePostStatus(
            found=found, status="published" if found else None, external_post_id=url, external_url=url
        )

    # -- analytics / engagement ----------------------------------------------------

    def get_analytics(self, credentials: Credentials, external_post_id: str) -> Analytics:
        with self.session(external_post_id) as page:
            metrics: dict[str, float | int] = {}
            likes = page.locator('a[href$="/liked_by/"]')
            if likes.count() and (n := parse_count(likes.first.inner_text())) is not None:
                metrics["likes"] = n
            plays = page.get_by_text(" plays").first
            if plays.count() and (n := parse_count(plays.inner_text())) is not None:
                metrics["views"] = n
        return Analytics(collected_at=datetime.now(UTC), metrics=metrics)

    def list_comments(
        self, credentials: Credentials, external_post_id: str, *, cursor: str | None = None, limit: int = 50
    ) -> CommentPage:
        out: list[RemoteComment] = []
        with self.session(external_post_id) as page:
            # Comment rows: <li> holding a profile link then the text. Row 0 is the caption.
            rows = page.locator("ul ul li, article ul > div > li")
            for i in range(min(rows.count(), limit)):
                row = rows.nth(i)
                author = row.locator("a").first
                if not author.count():
                    continue
                name = author.inner_text().strip()
                text = row.inner_text().strip().removeprefix(name).strip().splitlines()[0:1]
                if text:
                    out.append(RemoteComment(external_id=f"{i}:{name}", text=text[0], author_name=name))
        return CommentPage(comments=out)

    def reply_to_comment(
        self, credentials: Credentials, external_post_id: str, parent_comment_id: str, text: str
    ) -> RemoteComment:
        _, _, author = parent_comment_id.partition(":")
        with self.session(external_post_id) as page:
            box = page.get_by_role("textbox", name="Add a comment")
            box.fill(f"@{author} {text}" if author else text)
            pause(page)
            page.get_by_role("button", name="Post", exact=True).click()
            pause(page, 1500, 2500)
        return RemoteComment(external_id=f"own:{datetime.now(UTC).timestamp()}", text=text, is_own=True)

    def like_post(self, credentials: Credentials, external_post_id: str, *, like: bool = True) -> None:
        with self.session(external_post_id) as page:
            self._toggle(page, "Like", "Unlike", like)

    def like_comment(
        self, credentials: Credentials, external_post_id: str, comment_id: str, *, like: bool = True
    ) -> None:
        idx = int(comment_id.split(":", 1)[0])
        with self.session(external_post_id) as page:
            row = page.locator("ul ul li, article ul > div > li").nth(idx)
            self._toggle(row, "Like", "Unlike", like)

    @staticmethod
    def _toggle(scope: Any, like_label: str, unlike_label: str, like: bool) -> None:
        want, other = (like_label, unlike_label) if like else (unlike_label, like_label)
        button = scope.get_by_label(want, exact=True).first
        if button.count():
            button.click()
        elif not scope.get_by_label(other, exact=True).count():
            raise PlatformError("Instagram: could not find the like control (the page layout may have changed).")
