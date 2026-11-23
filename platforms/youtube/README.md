# YouTube (including Shorts)

**Status:** contract + media validation only. Publishing is not implemented.

- **API:** YouTube Data API v3. <https://developers.google.com/youtube/v3/guides/uploading_a_video>
- **Auth:** Google OAuth 2.0 (loopback/installed-app flow). Scope `https://www.googleapis.com/auth/youtube.upload`.
- **Publishing model:** `videos.insert` with a **resumable upload**. Persist the session URI as the upload reference so an interrupted upload can be resumed or reconciled instead of duplicated. Thumbnails use `thumbnails.set`.
- **Shorts:** not a separate API. Shorts are regular uploads of vertical (≤ 3 min) video. This adapter exposes a `shorts` variant (limits, metadata, export preset `youtube-short`) and **must not** be duplicated into a second publisher.
- **Quota:** the Data API is quota-limited (an upload costs a large share of the default daily quota). Unverified API projects may have uploads forced to private until audited.
- **Needs:** `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`.

Not yet done: OAuth flow, token storage/refresh, resumable upload, thumbnails, analytics.
