"""Media scanning, indexing and day-metadata synchronisation."""

from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO

from PIL import Image
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.config import AppConfig
from app.core.exceptions import (
    AppError,
    ConflictError,
    DependencyMissingError,
    NotFoundError,
    ValidationFailedError,
)
from app.core.paths import safe_join, to_project_relative
from app.database.base import new_id
from app.models import MediaAsset, Project
from app.pipeline.ffmpeg import check_binary, probe_file
from app.pipeline.sidecar import clip_id_for
from app.pipeline.stages.probe import ORIGINAL_360_EXTENSIONS, classify_media
from app.schemas.media import ScanResult
from app.services.listing import SortOrder, apply_sort, like_pattern
from app.tracking.events import append_event
from app.tracking.repository import ProjectRepository

_DAY_RE = re.compile(r"(?:^|/)(\d{4}-\d{2}-\d{2})(?:/|$)")
# "raw" = source video from any device or app; "stitched" = optional 360 exports.
_STAGE_BY_FOLDER = {"media/raw": "raw", "media/stitched": "stitched"}
_SCHEMA_TYPES = {"360", "360-stitched", "flat", "image", "unknown"}


def _stage_for(rel: str) -> str:
    for prefix, stage in _STAGE_BY_FOLDER.items():
        if rel.startswith(prefix + "/"):
            return stage
    for prefix, stage in (
        ("media/proxies/", "proxy"),
        ("media/thumbnails/", "thumbnail"),
        ("media/processed/", "processed"),
        ("media/ready/", "ready"),
        ("media/posted/", "posted"),
    ):
        if rel.startswith(prefix):
            return stage
    return "other"


def _day_for(rel: str, mtime: float) -> str:
    m = _DAY_RE.search(rel)
    if m:
        try:
            datetime.strptime(m.group(1), "%Y-%m-%d")
            return m.group(1)
        except ValueError:
            pass
    return datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")


#: Columns the media list can be sorted by (``?sort=``).
MEDIA_SORT = {
    "name": MediaAsset.relative_path,
    "day": MediaAsset.day,
    "size": MediaAsset.size_bytes,
    "added": MediaAsset.created_at,
}


class MediaService:
    def __init__(self, session: Session, config: AppConfig) -> None:
        self.session = session
        self.config = config

    # -- scanning ------------------------------------------------------------

    def scan(
        self,
        project: Project,
        *,
        probe: bool = True,
        is_cancelled: Any = lambda: False,
    ) -> ScanResult:
        root = Path(project.path).resolve()
        media_cfg = self.config.media
        ext_kind = {e.lower(): "video" for e in media_cfg.video_extensions}
        ext_kind.update({e.lower(): "image" for e in media_cfg.image_extensions})
        result = ScanResult()

        existing = {
            a.relative_path: a
            for a in self.session.scalars(select(MediaAsset).where(MediaAsset.project_id == project.id))
        }
        seen: set[str] = set()
        scanned_prefixes: list[str] = []

        for folder in media_cfg.scan_folders:
            base = safe_join(root, folder)
            if not base.is_dir():
                continue
            scanned_prefixes.append(folder.rstrip("/") + "/")
            for dirpath, dirnames, filenames in os.walk(base, followlinks=False):
                dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
                for name in sorted(filenames):
                    if name.startswith("."):
                        continue
                    kind = ext_kind.get(Path(name).suffix.lower())
                    if kind is None:
                        continue
                    full = Path(dirpath) / name
                    try:
                        resolved = full.resolve(strict=True)
                        rel = to_project_relative(resolved if full.is_symlink() else full, root)
                        st = resolved.stat()
                    except (OSError, AppError):
                        result.skipped += 1
                        result.warnings.append(f"Skipped {name}: unreadable or points outside the project.")
                        continue
                    if st.st_size > media_cfg.max_file_size_bytes:
                        result.skipped += 1
                        result.warnings.append(f"Skipped {rel}: larger than the configured limit.")
                        continue
                    seen.add(rel)
                    self._upsert(project, existing, rel, kind, st.st_size, st.st_mtime, result)
        self.session.flush()

        # Files that vanished from scanned folders.
        for rel, asset in existing.items():
            if rel in seen or not any(rel.startswith(p) for p in scanned_prefixes):
                continue
            if not asset.missing:
                asset.missing = True
                result.missing += 1

        if probe:
            self._probe_pending(project, root, result, is_cancelled)

        self.session.commit()
        result.days_written = self.sync_day_files(project)
        append_event(root, "media.scanned", result.model_dump(exclude={"warnings"}))
        return result

    def _upsert(
        self,
        project: Project,
        existing: dict[str, MediaAsset],
        rel: str,
        kind: str,
        size: int,
        mtime: float,
        result: ScanResult,
    ) -> None:
        asset = existing.get(rel)
        if asset is None:
            ext = "." + rel.rsplit(".", 1)[-1].lower()
            asset = MediaAsset(
                project_id=project.id,
                relative_path=rel,
                kind=kind,
                stage=_stage_for(rel),
                day=_day_for(rel, mtime),
                size_bytes=size,
                mtime=mtime,
                media_type="360" if ext in ORIGINAL_360_EXTENSIONS else ("unknown" if kind == "video" else "flat"),
            )
            self.session.add(asset)
            existing[rel] = asset
            result.new += 1
            return
        was_missing = asset.missing
        asset.missing = False
        if asset.size_bytes != size or asset.mtime != mtime:
            asset.size_bytes, asset.mtime = size, mtime
            asset.sha256 = None
            asset.probe = asset.probe_error = None
            asset.thumbnail_path = asset.proxy_path = None
            result.changed += 1
            result.warnings.append(
                f"{rel} changed on disk. Original footage should be immutable; derived files "
                "were detached and need regenerating (run the pipeline with force)."
            )
        elif was_missing:
            result.changed += 1
        else:
            result.unchanged += 1

    def _probe_pending(self, project: Project, root: Path, result: ScanResult, is_cancelled: Any) -> None:
        pending = list(
            self.session.scalars(
                select(MediaAsset).where(
                    MediaAsset.project_id == project.id,
                    MediaAsset.missing.is_(False),
                    MediaAsset.probe.is_(None),
                    MediaAsset.probe_error.is_(None),
                )
            )
        )
        ffprobe_ok = check_binary(self.config.pipeline.ffmpeg.ffprobe_binary) is not None
        if pending and not ffprobe_ok:
            result.warnings.append(
                "ffprobe was not found, so metadata was not extracted. Install FFmpeg "
                "(macOS: brew install ffmpeg, Debian/Ubuntu: sudo apt install ffmpeg) "
                "and scan again."
            )
        for asset in pending:
            if is_cancelled():
                break
            path = safe_join(root, asset.relative_path)
            try:
                if asset.kind == "image":
                    with Image.open(path) as im:
                        asset.probe = {"width": im.width, "height": im.height, "format": im.format}
                    asset.media_type = "flat"
                else:
                    if not ffprobe_ok:
                        continue
                    pr = probe_file(path, self.config.pipeline.ffmpeg)
                    asset.probe = pr.to_dict()
                    asset.media_type = classify_media(asset.relative_path, pr)
                    asset.camera = " ".join(p for p in (pr.make, pr.model) if p) or asset.camera
                result.probed += 1
            except DependencyMissingError:
                continue
            except Exception as exc:
                asset.probe_error = str(getattr(exc, "message", exc))[:1000]
                result.probe_failed += 1
                result.warnings.append(f"Could not probe {asset.relative_path}: {asset.probe_error}")

    # -- queries -------------------------------------------------------------

    def list_assets(
        self,
        project_id: str,
        *,
        kind: str | None = None,
        stage: str | None = None,
        day: str | None = None,
        postable: bool = False,
        q: str | None = None,
        media_type: str | None = None,
        day_from: str | None = None,
        day_to: str | None = None,
        sort: str | None = None,
        order: SortOrder = "desc",
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[MediaAsset], int]:
        query = select(MediaAsset).where(MediaAsset.project_id == project_id)
        if postable:  # picker data: real files you can attach to a post, not generated helpers
            query = query.where(MediaAsset.missing.is_(False), MediaAsset.stage.notin_(("proxy", "thumbnail")))
        if kind:
            query = query.where(MediaAsset.kind == kind)
        if stage:
            query = query.where(MediaAsset.stage == stage)
        if media_type:
            query = query.where(MediaAsset.media_type == media_type)
        if day:
            query = query.where(MediaAsset.day == day)
        if day_from:
            query = query.where(MediaAsset.day >= day_from)
        if day_to:
            query = query.where(MediaAsset.day <= day_to)
        if q and q.strip():
            pat = like_pattern(q)
            query = query.where(
                or_(
                    MediaAsset.relative_path.ilike(pat, escape="\\"),
                    MediaAsset.display_name.ilike(pat, escape="\\"),
                )
            )
        total = self.session.scalar(select(func.count()).select_from(query.subquery())) or 0
        query = apply_sort(
            query,
            MEDIA_SORT,
            sort,
            order,
            [MediaAsset.day.desc(), MediaAsset.relative_path],
            MediaAsset.id,
        )
        items = list(self.session.scalars(query.limit(limit).offset(offset)))
        return items, int(total)

    def rename(self, project_id: str, asset_id: str, display_name: str | None) -> MediaAsset:
        asset = self.get_asset(project_id, asset_id)
        if asset is None:
            raise NotFoundError("Media file not found.")
        name = (display_name or "").strip()
        if any(ord(c) < 32 for c in name):
            raise ValidationFailedError("Name must not contain control characters.")
        asset.display_name = name or None
        self.session.commit()
        return asset

    def add_upload(self, project: Project, filename: str, stream: BinaryIO) -> MediaAsset:
        """Copy an uploaded file into ``media/raw/<today>/`` and index it. Never overwrites."""
        cfg = self.config.media
        base = PurePosixPath(filename.replace("\\", "/")).name
        stem, dot, ext = base.rpartition(".")
        ext = f".{ext.lower()}" if dot else ""
        stem = re.sub(r"[^\w.\- ]+", "_", stem if dot else base).strip(" .") or "upload"
        stem = stem[:120]
        allowed = {e.lower() for e in (*cfg.video_extensions, *cfg.image_extensions)}
        if ext not in allowed:
            raise ValidationFailedError(
                f"'{ext or filename}' is not a supported video or image type.",
                details={"allowed": sorted(allowed)},
            )
        root = Path(project.path).resolve()
        folder = safe_join(root, "media/raw", datetime.now().strftime("%Y-%m-%d"))
        target = safe_join(folder, f"{stem}{ext}")
        if target.exists():
            raise ConflictError(f"'{target.name}' already exists in this project. Existing media is never overwritten.")
        folder.mkdir(parents=True, exist_ok=True)
        tmp = folder / f".upload-{new_id('tmp')}"
        written = 0
        try:
            with tmp.open("wb") as out:
                while chunk := stream.read(1024 * 1024):
                    written += len(chunk)
                    if written > cfg.max_file_size_bytes:
                        raise ValidationFailedError(f"File is larger than the {cfg.max_file_size_gb:g} GB limit.")
                    out.write(chunk)
            if written == 0:
                raise ValidationFailedError("The uploaded file is empty.")
            try:
                os.link(tmp, target)  # atomic, fails if it appeared meanwhile: never overwrites
            except FileExistsError as exc:
                raise ConflictError(f"'{target.name}' already exists in this project.") from exc
            except OSError:  # filesystem without hard links
                tmp.rename(target)
        finally:
            tmp.unlink(missing_ok=True)
        result = self.scan(project, probe=True)
        rel = to_project_relative(target, root)
        asset = self.session.scalar(
            select(MediaAsset).where(MediaAsset.project_id == project.id, MediaAsset.relative_path == rel)
        )
        if asset is None:
            raise ValidationFailedError(
                "The file was saved but could not be indexed.", details={"warnings": result.warnings}
            )
        return asset

    def get_asset(self, project_id: str, asset_id: str) -> MediaAsset | None:
        asset = self.session.get(MediaAsset, asset_id)
        return asset if asset is not None and asset.project_id == project_id else None

    # -- day metadata --------------------------------------------------------

    def sync_day_files(self, project: Project) -> int:
        """Write/merge ``data/days/YYYY-MM-DD.json`` from the media index.

        Existing clips are updated only in the fields derived from media
        (source info, thumbnail/proxy, status). Titles, outputs, posts and
        colour settings edited by the user are preserved, and clips are never
        deleted.
        """
        repo = ProjectRepository(Path(project.path))
        try:
            default_camera = (repo.read_project().get("settings") or {}).get("default_camera")
        except AppError:
            default_camera = None
        assets = list(
            self.session.scalars(
                select(MediaAsset).where(
                    MediaAsset.project_id == project.id,
                    MediaAsset.stage.in_(("raw", "stitched")),
                    MediaAsset.missing.is_(False),
                )
            )
        )
        by_day: dict[str, list[MediaAsset]] = {}
        for a in assets:
            if a.day:
                by_day.setdefault(a.day, []).append(a)

        written = 0
        for day, items in sorted(by_day.items()):
            try:
                doc = repo.read_day(day)
            except AppError:
                doc = {"date": day, "project_id": project.id, "clips": []}
            clips = {c["source"]["file"]: c for c in doc["clips"]}
            for a in sorted(items, key=lambda x: x.relative_path):
                clips[a.relative_path] = self._merge_clip(clips.get(a.relative_path), a, default_camera)
            doc["clips"] = [clips[k] for k in sorted(clips)]
            repo.write_day(day, doc)
            written += 1
        if written:
            repo.touch_index(day_count=len(repo.list_days()))
        return written

    @staticmethod
    def _merge_clip(clip: dict[str, Any] | None, a: MediaAsset, default_camera: str | None) -> dict[str, Any]:
        p = a.probe or {}
        meta = {
            "width": p.get("width"),
            "height": p.get("height"),
            "fps": p.get("fps"),
            "duration": p.get("duration"),
            "video_codec": p.get("video_codec"),
            "audio_codec": p.get("audio_codec"),
            "pixel_format": p.get("pixel_format"),
            "color_space": p.get("color_space"),
            "color_transfer": p.get("color_transfer"),
            "color_primaries": p.get("color_primaries"),
            "is_equirectangular": True if a.media_type == "360-stitched" else p.get("is_equirectangular"),
        }
        src_type = "image" if a.kind == "image" else (a.media_type if a.media_type in _SCHEMA_TYPES else "unknown")
        status = "pending"
        if a.probe:
            status = "completed" if (a.thumbnail_path and a.proxy_path) else "in_progress"
        source = {
            "file": a.relative_path,
            "type": src_type,
            # Metadata wins; the project's default camera fills the gap for any source.
            "camera": a.camera or default_camera,
            "sha256": a.sha256,
            "size_bytes": a.size_bytes,
            "metadata": meta if a.probe else None,
        }
        processing_update = {
            "status": status,
            "thumbnail": a.thumbnail_path,
            "proxy": a.proxy_path,
        }
        if clip is None:
            return {
                "id": clip_id_for(a.relative_path),
                "title": Path(a.relative_path).stem,
                "source": source,
                "processing": {
                    "color_profile": None,
                    "lut": None,
                    "edit_version": 0,
                    **processing_update,
                },
                "outputs": [],
                "posts": [],
            }
        clip["source"] = source
        clip["processing"] = {**clip.get("processing", {}), **processing_update}
        return clip
