# Adapter template

1. Copy this folder to `platforms/<name>/` and rename the class.
2. Set `name`, `display_name`, `env_vars`, `default_limits`.
3. Implement only the operations you can truly support against the **official**
   API; leave the rest to raise `UnsupportedOperationError` (the base class does).
4. Never log tokens; store them via `app.core.security.CredentialVault`.
5. Honour reconciliation: persist `upload_reference` before the transfer
   completes, and make `get_post_status` able to find a post by idempotency key,
   upload reference or external id.
6. Register: `platforms.registry.register(MyAdapter)`.
7. Add tests under `tests/platforms/` and a README describing API requirements.
