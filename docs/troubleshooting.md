# Troubleshooting

- Run `python -m app.cli doctor` first.
- **ffmpeg/ffprobe not found:** install FFmpeg and ensure it is on `PATH`.
- **Dashboard says API unreachable:** start the backend; check `NEXT_PUBLIC_API_URL` in `web/.env.local`; the API only
  accepts localhost Host headers.
- **`.osv` files skipped:** stitch in DJI Studio and place exports in `media/stitched/`.
- **Job stuck "running" after a crash:** restart the API; interrupted jobs are marked failed on startup.
- **AI says frames not allowed:** set `media_transmission.allow_frames: true` in `config/ai.yaml` or use `--allow-frames`.
- **Database errors:** back up `data/app.db` first (it holds jobs and post tracking), then re-run `python -m app.cli doctor`; deleting it loses job history and post records, but projects can be re-registered with `scan`.
