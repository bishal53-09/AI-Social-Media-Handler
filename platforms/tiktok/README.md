# TikTok

**Status:** contract + media validation only. Publishing is not implemented.

- **API:** Content Posting API. <https://developers.tiktok.com/doc/content-posting-api-get-started>
- **Auth:** TikTok Login Kit (OAuth 2.0). Scopes: `user.info.basic`, `video.upload`, `video.publish`.
- **App review / audit:** posts from unaudited apps are restricted (private visibility). Public posting requires TikTok's app review and a content-posting audit.
- **Publishing model:** initialise an upload, transfer the file (chunked), then poll publish status.
- **Needs:** `TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET`.
- **Limits** (see `config/platforms.yaml`; verify): up to 10 min, MP4/MOV/WebM.

Not yet done: OAuth flow, token storage/refresh, upload, status polling, analytics.
