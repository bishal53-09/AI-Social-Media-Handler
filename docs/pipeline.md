# Pipeline

| Stage | Status |
|---|---|
| ingest (SHA-256, registration) | implemented |
| probe (ffprobe; 360 detection via spherical metadata or 2:1 heuristic) | implemented |
| thumbnails (ffmpeg + Pillow) | implemented |
| proxies (progress, cancel, atomic output) | implemented |
| validation | implemented |
| color_grading, reframing, editing, subtitles, audio, rendering, analysis | **not implemented** (refuse to run) |

Multi-lens `.osv` originals are skipped for thumbnails/proxies: they need stitching in DJI Studio first, then place
the export in `media/stitched/`. Re-running skips completed, unchanged work. Failed files do not stop the run.
Run: `app.cli process <project>` or `POST /api/jobs`. Export presets: `config/export-presets.yaml`.
