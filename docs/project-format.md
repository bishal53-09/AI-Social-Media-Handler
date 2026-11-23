# Project format

Projects live outside the repo (default `MEDIA_ROOT`, e.g. `~/Content/<slug>`). Create with `init-project`.

```
project.json            # validated by config/schemas/project.schema.json
media/raw/              # source videos from any device or app (never modified);
                        #   optional <YYYY-MM-DD>/ subfolders set the day, else file date
media/stitched/         # optional: stitched 360 exports only
media/proxies/  media/thumbnails/
media/processed/{color-graded,reframed,edited,subtitles}/
media/ready/  media/posted/  media/references/  media/audio/
platforms/<platform>/...
data/                   # day.json, clip sidecars, analysis/ (JSON)
```

JSON files are written atomically and validated against Draft 2020-12 schemas (`config/schemas/`). Clip sidecars
record SHA-256, probe results, derived files and per-stage status. `scripts/validate_config.py <project>` validates a project.

## Colour handling (design note)
Four things are distinct and must never be conflated: the source's original colour profile, the colour space of any
export made from it (e.g. a stitched 360 export), the colour space a LUT expects as input, and the output colour space. Colour grading is **not
implemented**; this separation is the planned contract.

## Media types
`source.type` in a clip is `flat` for any ordinary video (phone, camera, drone, screen recording, finished edit, in
any orientation). 360 is opt-in: `360` marks `.osv`/`.insv` camera originals, and `360-stitched` marks a video with
spherical metadata, or a 2:1 video placed in `media/stitched/`. A 2:1 video anywhere else stays `flat`, with a
probe warning.
