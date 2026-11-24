# Platform integrations

Contract: `platforms/base.py` (capabilities, media validation, auth, publish, status/reconcile, analytics).

## Browser sessions instead of API keys (experimental)

Instagram, TikTok and YouTube (Shorts as a variant) are driven through **your own logged-in browser profile**
(`platforms/browser.py`, Playwright). There is no Meta app, TikTok developer app or Google OAuth client.

```bash
pip install -e '.[browser]' && playwright install chromium
python -m app.cli login instagram      # visible window: sign in by hand, then close it
python -m app.cli session-status       # which platforms are still signed in
```

Set `handle` for Instagram and TikTok in `config/platforms.yaml` (used to find a freshly published post). Cookies live in
`BROWSER_PROFILE_DIR` (default `~/.asmh/browser-profiles`), outside the repo; passwords are never seen by this code.
`POST /posts/{id}/publish` publishes an approved, queued post. Posts are identified by their URL.

Covered per platform (all `experimental`, none verified against the live sites yet): publish, public-count analytics
(likes/comments/plays/views), list comments, reply, like post; Instagram also likes comments. Hide/delete comments,
reach/impressions and private insights are `unavailable`.

Risks, plainly: automating these sites can breach their terms and get the account restricted (Instagram and TikTok
detect automation; likes and comments are the riskiest); selectors break whenever a site changes its markup, and then
the call fails loudly instead of returning fake data; Google may refuse sign-in inside an automated browser. YouTube's
official Data API would be more reliable, and could be swapped in behind the same adapter.

Publishing rules (enforced by `PostService`): draft → approved → queued → uploading → processing → published; also
failed, unknown, cancelled. An idempotency key is stored before upload; an `unknown` post can only be resolved by
reconciling with the platform, never by blind retry.

## Engagement: comments, interactions and analytics

The app is a manager, not only a poster. The adapter contract (`platforms/base.py`) therefore also covers:
`list_comments`, `reply_to_comment`, `like_comment`, `set_comment_hidden`, `delete_comment`, `like_post` and
`get_analytics`. Each adapter declares per capability one of three states, shown in the UI and `GET /settings`:

| State | Meaning |
|---|---|
| `implemented` | Real adapter code verified against the live platform. **None yet.** |
| `experimental` | Browser-session code exists but has not been verified against the live site. |
| `planned` | Possible, but not built. |
| `unavailable` | Not supported for this platform. |

Behaviour guarantees (tested with a fake adapter): sync stores comments and a metric snapshot per sync (history kept);
comments removed on the platform are flagged, not silently dropped; every interaction attempted is written to an audit
trail (`engagement_actions`) with errors redacted; unsupported operations fail with `501` *before* anything is sent;
unexpected platform failures surface as `502 platform_error`. If the browser is unavailable or signed out, a sync reports the error
and shows no data; nothing is simulated.

Browser adapters need no tokens: the default credentials resolver supplies identity only and the session lives in the
browser profile.
