# Contributing

1. Fork, create a branch, run `bash setup.sh` in your checkout.
2. Keep changes focused; add tests (`make test`). `make check` must pass (ruff, mypy, pytest, eslint, tsc, prettier).
3. Never commit secrets, footage, generated media, databases or real project metadata (`.gitignore` blocks most).
4. Documentation must not describe planned features as implemented. Unfinished stages must refuse to run.
5. New platform integrations: copy `platforms/_template/` and follow `platforms/README.md`.
6. Open a pull request using the template. Be kind: see the [Code of Conduct](CODE_OF_CONDUCT.md).
