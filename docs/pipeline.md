# Pipeline

| Stage | Status |
|---|---|
| ingest (SHA-256, registration) | implemented |
| probe (ffprobe; any readable video; 360 only from spherical metadata or a 2:1 file in `media/stitched/`) | implemented |
| thumbnails (ffmpeg + Pillow) | implemented |
| proxies (progress, cancel, atomic output) | implemented |
| validation | implemented |
| color_grading, reframing, editing, subtitles, audio, rendering, analysis | **not implemented** (refuse to run) |

Any ordinary video goes through every implemented stage. Proxies cap the shorter side at `proxies.height` (540 by
default), so vertical 9:16 phone video gets the same quality as landscape; 360 exports use `equirect_height`.
Optional 360 workflow: multi-lens `.osv`/`.insv` originals are skipped for thumbnails/proxies until they are stitched
in the camera vendor's software (e.g. DJI Studio, Insta360 Studio) and the export is placed in `media/stitched/`. Re-running skips completed, unchanged work. Failed files do not stop the run.
Run: `app.cli process <project>` or `POST /api/jobs`. Export presets: `config/export-presets.yaml`.
