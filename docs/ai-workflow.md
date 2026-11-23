# AI workflow

AI returns **plans** (strict pydantic schemas, `extra="forbid"`, then semantic validation such as time ranges inside
clip duration); deterministic code executes them. Provider abstraction: `app/ai/base.py`; `AnthropicProvider` uses the
official SDK. Implemented modules: footage analysis, highlight detection, edit planning, caption generation (prompts in
`app/ai/prompts/*.md`). Only `analyze` is wired to the CLI.

Privacy: whole videos are never uploaded. Sampled, downscaled frames (EXIF stripped) are sent only if
`media_transmission.allow_frames` is true or `--allow-frames` is passed. **Not verified against the live API** in this
milestone (unit-tested with fakes). Executing edit plans is not implemented.
