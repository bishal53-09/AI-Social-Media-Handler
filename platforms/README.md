# Platform adapters

Every social platform lives in its own package and implements
[`PlatformAdapter`](base.py). Adapters are independent and replaceable: the
application only talks to the interface, and platforms never import each other.

| Platform  | Contract | Media validation | Auth | Publish | Analytics |
|-----------|----------|------------------|------|---------|-----------|
| Instagram | ✅ | ✅ (Reels limits) | ❌ not implemented | ❌ | ❌ |
| TikTok    | ✅ | ✅ | ❌ | ❌ | ❌ |
| YouTube   | ✅ | ✅ (video + Shorts) | ❌ | ❌ | ❌ |
| Facebook / LinkedIn / X | documentation only | – | – | – | – |

**Nothing publishes yet.** Calling `authenticate()`, `publish()`,
`get_post_status()` or `get_analytics()` raises `UnsupportedOperationError`
with a pointer to the platform README. Real publishing (Phase 6) must use the
official platform APIs only.

## Interface

```python
class PlatformAdapter(ABC):
    def validate_media(path, probe, variant=None) -> MediaValidation   # implemented
    def authenticate() -> Credentials                                  # TODO
    def refresh_credentials(credentials) -> Credentials                # TODO
    def publish(credentials, request) -> PublishResult                 # TODO
    def get_post_status(credentials, ...) -> RemotePostStatus          # TODO (reconciliation)
    def get_analytics(credentials, external_post_id) -> Analytics      # TODO
```

`validate_media` is real: it checks container, size, duration, aspect ratio and
refuses un-reframed equirectangular video, using limits from
`config/platforms.yaml`.

## Adding a platform

Copy [`_template/`](_template/), implement the methods you can support, and
register the class with `platforms.registry.register`. See
[docs/platform-integrations.md](../docs/platform-integrations.md) for the
publishing state machine and the reconciliation rules every adapter must honour.
