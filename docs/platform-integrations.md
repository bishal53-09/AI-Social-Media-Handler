# Platform integrations

Contract: `platforms/base.py` (capabilities, media validation, auth, publish, status/reconcile, analytics).
Instagram, TikTok and YouTube (Shorts as a variant) implement **media validation and metadata only**; auth, publish and
analytics raise `UnsupportedOperationError`. Facebook, LinkedIn and X have README stubs. Add a platform by copying
`platforms/_template/`.

Publishing rules (enforced by `PostService`): draft → approved → queued → uploading → processing → published; also
failed, unknown, cancelled. An idempotency key is stored before upload; an `unknown` post can only be resolved by
reconciling with the platform, never by blind retry. Instagram will need publicly reachable media URLs (object storage;
`app/storage/object_storage.py` is an interface only).

## Engagement: comments, interactions and analytics

The app is a manager, not only a poster. The adapter contract (`platforms/base.py`) therefore also covers:
`list_comments`, `reply_to_comment`, `like_comment`, `set_comment_hidden`, `delete_comment`, `like_post` and
`get_analytics`. Each adapter declares per capability one of three states, shown in the UI and `GET /settings`:

| State | Meaning |
|---|---|
| `implemented` | Real, tested adapter code exists. **No capability is implemented yet on any platform.** |
| `planned` | The platform's official API appears to allow it; the adapter does not do it yet. |
| `unavailable` | The official API does not offer it (or only to restricted programs). |

The `planned`/`unavailable` declarations are our best reading of the platform docs and **must be re-verified against
current documentation and quotas when implementing**: YouTube (list/reply/moderate/delete comments, like a video,
no comment likes), Instagram (list/reply/hide/delete comments, no likes), TikTok (basic statistics only; comment
management needs restricted programs).

Behaviour guarantees (tested with a fake adapter): sync stores comments and a metric snapshot per sync (history kept);
comments removed on the platform are flagged, not silently dropped; every interaction attempted is written to an audit
trail (`engagement_actions`) with errors redacted; unsupported operations fail with `501` *before* anything is sent;
unexpected platform failures surface as `502 platform_error`. With the shipped adapters a sync reports "not implemented"
and shows no data; nothing is simulated.

Credentials for engagement calls come from a resolver (`EngagementService(credentials_for=...)`); until OAuth is
implemented the default resolver supplies identity only, no tokens.
