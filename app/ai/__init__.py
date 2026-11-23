"""AI editing-director layer.

Boundaries (see docs/ai-workflow.md):

* The model **plans**; deterministic code **executes**. Responses are
  structured JSON validated against strict schemas — there is no field through
  which the model can supply a shell command or a file path.
* Media leaves the machine only as sampled, downscaled, metadata-stripped
  frames, and only when ``config/ai.yaml: media_transmission.allow_frames`` is
  true. Whole videos are never uploaded.
"""
