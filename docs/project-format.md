# Project format

Projects live outside the repo (default `MEDIA_ROOT`, e.g. `~/Content/<slug>`). Create with `init-project`.

```
project.json            # validated by config/schemas/project.schema.json
media/raw/<YYYY-MM-DD>/ # camera originals (never modified)
media/stitched/         # externally stitched 360 exports
media/proxies/  media/thumbnails/
media/processed/{color-graded,reframed,edited,subtitles}/
media/ready/  media/posted/  media/references/  media/audio/
platforms/<platform>/...
data/                   # day.json, clip sidecars, analysis/ (JSON)
```

JSON files are written atomically and validated against Draft 2020-12 schemas (`config/schemas/`). Clip sidecars
record SHA-256, probe results, derived files and per-stage status. `scripts/validate_config.py <project>` validates a project.

## Colour handling (design note)
Four things are distinct and must never be conflated: the camera's original colour profile, the colour space of any
stitched export, the colour space a LUT expects as input, and the output colour space. Colour grading is **not
implemented**; this separation is the planned contract.
