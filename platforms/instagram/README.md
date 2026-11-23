# Instagram

**Status:** contract + media validation only. Publishing is not implemented.

- **API:** Instagram Graph API (Meta). <https://developers.facebook.com/docs/instagram-platform/content-publishing/>
- **Account:** an Instagram *professional* (Business or Creator) account linked to a Facebook Page.
- **Auth:** Meta Login OAuth. Scopes typically include `instagram_basic` and `instagram_content_publish`. Long-lived tokens expire and must be refreshed.
- **Publishing model:** create a media container from a **publicly reachable video URL**, poll until it is `FINISHED`, then publish it. The application never exposes footage publicly on its own; configure `S3_*` (or another host) and approve each upload.
- **Limits** (see `config/platforms.yaml`; verify against current docs): Reels 3 s – 15 min, 9:16, MP4/MOV.
- **Needs:** `META_APP_ID`, `META_APP_SECRET`; a Meta app (and, for other users' accounts, app review).
- **Rate limits:** content-publishing is rate-limited per account per day.

Not yet done: OAuth flow, token storage/refresh, container creation, publish, insights.
