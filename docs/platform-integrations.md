# Platform integrations

Contract: `platforms/base.py` (capabilities, media validation, auth, publish, status/reconcile, analytics).
Instagram, TikTok and YouTube (Shorts as a variant) implement **media validation and metadata only**; auth, publish and
analytics raise `UnsupportedOperationError`. Facebook, LinkedIn and X have README stubs. Add a platform by copying
`platforms/_template/`.

Publishing rules (enforced by `PostService`): draft → approved → queued → uploading → processing → published; also
failed, unknown, cancelled. An idempotency key is stored before upload; an `unknown` post can only be resolved by
reconciling with the platform, never by blind retry. Instagram will need publicly reachable media URLs (object storage;
`app/storage/object_storage.py` is an interface only).
