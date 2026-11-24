"""Project lifecycle: creation on disk, registration in SQLite, lookup."""

from __future__ import annotations

import re
import unicodedata
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.config import AppConfig, Settings
from app.core.exceptions import ConflictError, NotFoundError, PathSecurityError
from app.core.paths import expand, is_within
from app.models import MediaAsset, Project
from app.schemas.project import ProjectMetadata, ProjectSettings
from app.services.listing import SortOrder, apply_sort, like_pattern
from app.tracking.events import append_event
from app.tracking.repository import ProjectRepository

# Complete layout created by `init-project` (see docs/project-format.md).
PROJECT_DIRS: tuple[str, ...] = (
    "media/raw",
    "media/stitched",
    "media/proxies",
    "media/processed/color-graded",
    "media/processed/reframed",
    "media/processed/edited",
    "media/processed/subtitles",
    "media/ready",
    "media/posted",
    "media/references/videos",
    "media/references/images",
    "media/references/trend-notes",
    "media/audio/music",
    "media/audio/sound-effects",
    "media/audio/voiceovers",
    "media/thumbnails",
    "platforms/instagram/reels",
    "platforms/instagram/stories",
    "platforms/tiktok/videos",
    "platforms/youtube/videos",
    "platforms/youtube/thumbnails",
    "platforms/youtube-shorts",
    "platforms/facebook",
    "platforms/linkedin",
    "data/days",
    "data/jobs",
    "data/trends",
    "data/analytics",
    "data/exports",
    "exports/drafts",
    "exports/approved",
    "exports/published",
    "logs",
)

_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")


def slugify(name: str) -> str:
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60].strip("-")
    return slug or "project"


#: Columns the project list can be sorted by (``?sort=``).
PROJECT_SORT = {"name": Project.name, "created": Project.created_at, "updated": Project.updated_at}


class ProjectService:
    def __init__(self, session: Session, settings: Settings, config: AppConfig) -> None:
        self.session = session
        self.settings = settings
        self.config = config

    # -- paths ---------------------------------------------------------------

    def allowed_roots(self) -> list[Path]:
        roots = [self.settings.media_root_path]
        roots.extend(expand(r) for r in self.config.projects.allowed_roots)
        return roots

    def _check_allowed(self, path: Path) -> None:
        if not any(is_within(path, root) for root in self.allowed_roots()):
            raise PathSecurityError(
                "Project path is outside the allowed project roots.",
                details={"path": str(path), "allowed_roots": [str(r) for r in self.allowed_roots()]},
            )

    # -- create / register ---------------------------------------------------

    def _unique_id(self, base: str) -> str:
        candidate, n = base, 2
        while self.session.get(Project, candidate) is not None:
            candidate = f"{base[:58]}-{n}"
            n += 1
        return candidate

    def init_project(
        self,
        name: str,
        path: str | Path | None = None,
        *,
        description: str | None = None,
        default_camera: str | None = None,
        enforce_roots: bool = False,
    ) -> Project:
        """Create a project directory tree and register it.

        Existing files are never overwritten. An existing, non-empty directory
        is accepted (missing folders are added) unless it already holds a
        ``project.json``.
        """
        slug = slugify(name)
        root = expand(path) if path else (self.settings.media_root_path / slug).resolve()
        if enforce_roots:
            self._check_allowed(root)
        if root.exists() and not root.is_dir():
            raise ConflictError(f"{root} exists and is not a directory.")
        repo = ProjectRepository(root)
        if repo.exists():
            raise ConflictError(
                f"{root} already contains a project. Use a new path, or register it with "
                "'scan' to index the existing project.",
                details={"path": str(root)},
            )
        if self.session.scalar(select(Project).where(Project.path == str(root))):
            raise ConflictError("A project is already registered at this path.")

        for rel in PROJECT_DIRS:
            (root / rel).mkdir(parents=True, exist_ok=True)

        now = datetime.now(UTC)
        project_id = self._unique_id(slug)
        meta = ProjectMetadata(
            id=project_id,
            name=name,
            description=description,
            created_at=now,
            updated_at=now,
            settings=ProjectSettings(default_camera=default_camera),
        )
        repo.write_project(meta.model_dump(mode="json"))
        repo.touch_index(project_id=project_id, name=name, schema_version=1)
        append_event(root, "project.created", {"id": project_id, "name": name})

        project = Project(
            id=project_id,
            name=name,
            path=str(root),
            description=description,
            created_at=now,
            updated_at=now,
        )
        self.session.add(project)
        self.session.commit()
        return project

    def register(self, path: str | Path) -> Project:
        """Index an existing project folder (e.g. one copied from another computer)."""
        root = expand(path)
        repo = ProjectRepository(root)
        meta = repo.read_project()
        existing = self.session.scalar(select(Project).where(Project.path == str(root)))
        if existing:
            return existing
        pid = meta["id"]
        if not _ID_RE.match(pid):
            raise ConflictError("project.json has an invalid id.")
        if self.session.get(Project, pid) is not None:
            raise ConflictError(
                f"A different project with id '{pid}' is already registered.",
                details={"path": str(root)},
            )
        project = Project(
            id=pid,
            name=meta["name"],
            path=str(root),
            description=meta.get("description"),
        )
        self.session.add(project)
        self.session.commit()
        return project

    def get_or_register(self, path: str | Path) -> Project:
        root = expand(path)
        existing = self.session.scalar(select(Project).where(Project.path == str(root)))
        return existing or self.register(root)

    # -- queries -------------------------------------------------------------

    def list_projects(
        self,
        *,
        q: str | None = None,
        sort: str | None = None,
        order: SortOrder = "desc",
        limit: int | None = None,
        offset: int = 0,
    ) -> tuple[list[Project], int]:
        query = select(Project)
        if q and q.strip():
            pat = like_pattern(q)
            query = query.where(or_(Project.name.ilike(pat, escape="\\"), Project.description.ilike(pat, escape="\\")))
        total = self.session.scalar(select(func.count()).select_from(query.subquery())) or 0
        query = apply_sort(query, PROJECT_SORT, sort, order, [Project.created_at.desc()], Project.id)
        query = query.offset(offset)
        if limit is not None:
            query = query.limit(limit)
        return list(self.session.scalars(query)), int(total)

    def get(self, project_id: str) -> Project:
        project = self.session.get(Project, project_id)
        if project is None:
            raise NotFoundError(f"Project '{project_id}' not found.")
        return project

    def repository(self, project: Project) -> ProjectRepository:
        return ProjectRepository(Path(project.path))

    def counts(self, project: Project) -> tuple[int, int]:
        days = len(self.repository(project).list_days())
        media = self.session.scalar(
            select(func.count())
            .select_from(MediaAsset)
            .where(MediaAsset.project_id == project.id, MediaAsset.missing.is_(False))
        )
        return days, int(media or 0)
