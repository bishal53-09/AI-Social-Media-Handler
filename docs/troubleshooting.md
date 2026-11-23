# Troubleshooting

- Run `python -m app.cli doctor` first.
- **ffmpeg/ffprobe not found:** install FFmpeg and ensure it is on `PATH`.
- **Dashboard says API unreachable:** start the backend; check `NEXT_PUBLIC_API_URL` in `web/.env.local`; the API only
  accepts localhost Host headers.
- **`.osv` files skipped:** stitch in DJI Studio and place exports in `media/stitched/`.
- **Job stuck "running" after a crash:** restart the API; interrupted jobs are marked failed on startup.
- **AI says frames not allowed:** set `media_transmission.allow_frames: true` in `config/ai.yaml` or use `--allow-frames`.
- **Database errors:** `data/app.db` can be deleted safely; it is rebuilt (project JSON is the source of truth, then re-run `scan`).
