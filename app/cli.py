"""Command-line interface: ``python -m app.cli --help``."""

from __future__ import annotations

import os
import platform
import re
import shutil
import stat
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

import typer
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import __version__
from app.core.config import AppConfig, Settings, get_app_config, get_settings, load_app_config
from app.core.exceptions import AppError
from app.core.logging import setup_logging
from app.core.paths import REPO_ROOT, expand
from app.database.migrate import upgrade_database
from app.database.session import Database
from app.models import Project

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="AI Social Media Handler — local-first video production and publishing.",
)


@contextmanager
def _db_session() -> Iterator[tuple[Session, Settings, AppConfig]]:
    settings, config = get_settings(), get_app_config()
    upgrade_database(settings.resolved_database_url)
    db = Database(settings.resolved_database_url)
    session = db.session()
    try:
        yield session, settings, config
    finally:
        session.close()
        db.dispose()


def _fail(exc: AppError) -> typer.Exit:
    typer.secho(f"Error: {exc.message}", fg=typer.colors.RED, err=True)
    for key, value in exc.details.items():
        typer.echo(f"  {key}: {value}", err=True)
    return typer.Exit(1)


# ---------------------------------------------------------------------------
# version
# ---------------------------------------------------------------------------


@app.command()
def version() -> None:
    """Print the version."""
    typer.echo(f"ai-social-media-handler {__version__}")


# ---------------------------------------------------------------------------
# doctor
# ---------------------------------------------------------------------------


@dataclass
class Check:
    name: str
    status: str  # ok | warn | fail
    detail: str
    fix: str | None = None


def _tool_version(binary: str, args: list[str]) -> tuple[str | None, str | None]:
    path = shutil.which(binary)
    if not path:
        return None, None
    try:
        out = subprocess.run([path, *args], capture_output=True, text=True, timeout=15, check=False).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return path, None
    return path, out.splitlines()[0] if out else None


def run_checks() -> list[Check]:
    checks: list[Check] = []
    install_hint = (
        "brew install {0}"
        if platform.system() == "Darwin"
        else "sudo apt install {0}  (or your distro's package manager)"
    )

    v = sys.version_info
    checks.append(
        Check(
            "Python",
            "ok" if v >= (3, 11) else "fail",
            f"{v.major}.{v.minor}.{v.micro}",
            None if v >= (3, 11) else "Python 3.11 or newer is required.",
        )
    )

    _, git_v = _tool_version("git", ["--version"])
    checks.append(
        Check("Git", "ok" if git_v else "warn", git_v or "not found", None if git_v else install_hint.format("git"))
    )

    for name, binary in (("FFmpeg", "ffmpeg"), ("ffprobe", "ffprobe")):
        path, ver = _tool_version(binary, ["-version"])
        checks.append(
            Check(
                name,
                "ok" if path else "fail",
                ver or "not found",
                None if path else f"Required for media processing. {install_hint.format('ffmpeg')}",
            )
        )

    _, node_v = _tool_version("node", ["--version"])
    node_ok = bool(node_v and (m := re.match(r"v(\d+)", node_v)) and int(m.group(1)) >= 20)
    checks.append(
        Check(
            "Node.js",
            "ok" if node_ok else "warn",
            node_v or "not found",
            None
            if node_ok
            else "Node.js 20+ is needed for the dashboard only. "
            "Install from https://nodejs.org/ or your package manager.",
        )
    )
    _, npm_v = _tool_version("npm", ["--version"])
    checks.append(
        Check(
            "npm",
            "ok" if npm_v else "warn",
            npm_v or "not found",
            None if npm_v else "npm ships with Node.js; needed for the dashboard only.",
        )
    )

    # Configuration
    settings: Settings | None = None
    try:
        settings = get_settings()
        cfg = load_app_config(settings.config_path)
        checks.append(
            Check(
                "Configuration",
                "ok",
                f"{len(cfg.pipeline.stages)} pipeline stages, {len(cfg.export_presets)} export presets",
            )
        )
    except Exception as exc:
        checks.append(
            Check("Configuration", "fail", str(exc), "Fix the file named above, or restore it from the repository.")
        )

    env_file = REPO_ROOT / ".env"
    if env_file.exists():
        mode = stat.S_IMODE(env_file.stat().st_mode)
        if mode & 0o077:
            checks.append(Check(".env permissions", "warn", f"mode {mode:o}", f"chmod 600 {env_file}"))
        else:
            checks.append(Check(".env permissions", "ok", "owner-only (600)"))
    else:
        checks.append(Check(".env", "warn", "not found", "cp .env.example .env && chmod 600 .env"))

    if settings:
        checks.append(
            Check(
                "Server binding",
                "ok" if settings.is_localhost_bind else "warn",
                f"{settings.app_host}:{settings.app_port}",
                None
                if settings.is_localhost_bind
                else "Bound beyond localhost: anyone on your network can reach the API. Set APP_HOST=127.0.0.1.",
            )
        )
        has_key = settings.anthropic_api_key is not None
        checks.append(
            Check(
                "Anthropic API key",
                "ok" if has_key else "warn",
                "configured" if has_key else "not set",
                None if has_key else "Only needed for AI features: set ANTHROPIC_API_KEY in .env.",
            )
        )
        # Database
        try:
            upgrade_database(settings.resolved_database_url)
            db = Database(settings.resolved_database_url)
            with db.transaction() as s:
                n = s.scalar(select(func.count()).select_from(Project))
            db.dispose()
            checks.append(Check("Database", "ok", f"initialised ({n} project(s))"))
        except Exception as exc:
            checks.append(
                Check(
                    "Database", "fail", str(exc)[:200], "Check DATABASE_URL and that the data/ directory is writable."
                )
            )
        # Project directory
        root = settings.media_root_path
        probe = root
        while not probe.exists() and probe != probe.parent:
            probe = probe.parent
        writable = os.access(probe, os.W_OK)
        checks.append(
            Check(
                "Project directory",
                "ok" if writable else "fail",
                f"{root} ({'exists' if root.exists() else 'will be created'}, "
                f"{'writable' if writable else 'NOT writable'})",
                None if writable else f"Make {probe} writable or set MEDIA_ROOT in .env.",
            )
        )
    return checks


@app.command()
def doctor() -> None:
    """Check the environment and report anything that needs attention."""
    icons = {"ok": ("✓", typer.colors.GREEN), "warn": ("!", typer.colors.YELLOW), "fail": ("✗", typer.colors.RED)}
    checks = run_checks()
    for c in checks:
        icon, color = icons[c.status]
        typer.secho(f" {icon} {c.name:<20} {c.detail}", fg=color)
        if c.fix:
            typer.echo(f"     → {c.fix}")
    failed = [c for c in checks if c.status == "fail"]
    warned = [c for c in checks if c.status == "warn"]
    typer.echo("")
    if failed:
        typer.secho(f"{len(failed)} problem(s) must be fixed.", fg=typer.colors.RED)
        raise typer.Exit(1)
    typer.secho(
        "Everything required is in place." + (f" {len(warned)} optional item(s) need attention." if warned else ""),
        fg=typer.colors.GREEN,
    )


# ---------------------------------------------------------------------------
# projects
# ---------------------------------------------------------------------------


@app.command("init-project")
def init_project(
    name: str = typer.Option(..., "--name", help="Human-readable project name."),
    path: str = typer.Option(None, "--path", help="Project directory (default: <MEDIA_ROOT>/<slug>)."),
    description: str = typer.Option(None, "--description"),
    camera: str = typer.Option(None, "--camera", help='Default camera, e.g. "DJI Osmo 360 II".'),
) -> None:
    """Create a project directory tree with metadata and register it."""
    from app.services.project_service import ProjectService

    try:
        with _db_session() as (session, settings, config):
            project = ProjectService(session, settings, config).init_project(
                name, path, description=description, default_camera=camera
            )
    except AppError as exc:
        raise _fail(exc) from exc
    typer.secho(f"Created project '{project.name}' ({project.id})", fg=typer.colors.GREEN)
    typer.echo(f"  Location: {project.path}")
    typer.echo("  Put camera originals in media/raw/<YYYY-MM-DD>/ and stitched exports in media/stitched/.")
    typer.echo(f"  Next: python -m app.cli scan {project.path}")


@app.command()
def scan(
    path: str = typer.Argument(..., help="Project directory."),
    no_probe: bool = typer.Option(False, "--no-probe", help="Index files without running ffprobe."),
) -> None:
    """Index media files, extract metadata and update the daily JSON files."""
    from app.services.media_service import MediaService
    from app.services.project_service import ProjectService

    try:
        with _db_session() as (session, settings, config):
            project = ProjectService(session, settings, config).get_or_register(path)
            result = MediaService(session, config).scan(project, probe=not no_probe)
    except AppError as exc:
        raise _fail(exc) from exc
    typer.echo(
        f"new: {result.new}  changed: {result.changed}  unchanged: {result.unchanged}  "
        f"missing: {result.missing}  skipped: {result.skipped}"
    )
    typer.echo(
        f"probed: {result.probed}  probe failures: {result.probe_failed}  day files written: {result.days_written}"
    )
    for w in result.warnings:
        typer.secho(f"  ! {w}", fg=typer.colors.YELLOW)


@app.command()
def process(
    path: str = typer.Argument(..., help="Project directory (must be scanned first)."),
    stages: list[str] = typer.Option(
        None,
        "--stage",
        "-s",
        help="Stage to run (repeatable). Default: ingest, probe, thumbnails, proxies, validation.",
    ),
    force: bool = typer.Option(False, "--force", help="Regenerate existing thumbnails/proxies."),
) -> None:
    """Run the processing pipeline (thumbnails, proxies, ...) and wait for it to finish."""
    from app.models import Job
    from app.pipeline.orchestrator import PipelineRunner, resolve_stages
    from app.services.project_service import ProjectService

    try:
        resolve_stages(stages or None)
        with _db_session() as (session, settings, config):
            project = ProjectService(session, settings, config).get_or_register(path)
            job = Job(type="pipeline.process", project_id=project.id, params={"stages": stages or None, "force": force})
            session.add(job)
            session.commit()
            PipelineRunner(session, config).run(job.id)
            session.refresh(job)
            result, status, error = job.result or {}, job.status, job.error
    except AppError as exc:
        raise _fail(exc) from exc
    for info in (result.get("assets") or {}).values():
        mark = "✓" if info["ok"] else "✗"
        typer.echo(f" {mark} {info['path']}  " + " ".join(f"{k}={v}" for k, v in info["stages"].items()))
        if info.get("error"):
            typer.secho(f"     {info['error']}", fg=typer.colors.RED)
    typer.echo(f"job {status}: {result.get('succeeded', 0)} ok, {result.get('failed', 0)} failed")
    if status != "completed":
        if error:
            typer.secho(error, fg=typer.colors.RED, err=True)
        raise typer.Exit(1)


def _human(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


@app.command()
def inventory(path: str = typer.Argument(..., help="Project directory.")) -> None:
    """Summarise a project's indexed media."""
    from app.models import MediaAsset
    from app.services.project_service import ProjectService

    try:
        with _db_session() as (session, settings, config):
            svc = ProjectService(session, settings, config)
            project = svc.get_or_register(path)
            assets = list(
                session.scalars(
                    select(MediaAsset)
                    .where(MediaAsset.project_id == project.id, MediaAsset.missing.is_(False))
                    .order_by(MediaAsset.relative_path)
                )
            )
            days = svc.repository(project).list_days()
    except AppError as exc:
        raise _fail(exc) from exc
    typer.echo(f"Project: {project.name} ({project.id})\nPath:    {project.path}")
    if not assets:
        typer.echo(f"\nNo media indexed yet. Run: python -m app.cli scan {project.path}")
        return
    total = sum(a.size_bytes for a in assets)
    typer.echo(f"\n{len(assets)} file(s), {_human(total)}, {len(days)} day file(s)\n")
    by_stage: dict[str, int] = {}
    for a in assets:
        by_stage[a.stage] = by_stage.get(a.stage, 0) + 1
    typer.echo("By stage: " + ", ".join(f"{k}={v}" for k, v in sorted(by_stage.items())))
    typer.echo(f"\n{'FILE':<52} {'TYPE':<13} {'RES':<11} {'FPS':>5} {'DUR':>7}  PROXY")
    for a in assets:
        p = a.probe or {}
        res = f"{p.get('width')}x{p.get('height')}" if p.get("width") else "-"
        dur = f"{p['duration']:.1f}s" if p.get("duration") is not None else "-"
        fps = f"{p['fps']:.2f}" if p.get("fps") else "-"
        err = f"  (probe failed: {a.probe_error[:60]})" if a.probe_error else ""
        typer.echo(
            f"{a.relative_path[-52:]:<52} {a.media_type:<13} {res:<11} {fps:>5} {dur:>7}  "
            f"{'yes' if a.proxy_path else 'no'}{err}"
        )


@app.command()
def analyze(
    path: str = typer.Argument(..., help="Project directory."),
    clip: str = typer.Argument(..., help="Media id or project-relative path."),
    allow_frames: bool = typer.Option(
        False, "--allow-frames", help="Consent to sending a few downscaled frames of this clip to the AI provider."
    ),
) -> None:
    """Analyse one clip with the configured AI provider (sends sampled frames)."""
    from app.ai.registry import get_provider
    from app.services.analysis_service import analyze_asset
    from app.services.project_service import ProjectService

    try:
        with _db_session() as (session, settings, config):
            if allow_frames:
                config.ai.media_transmission.allow_frames = True
            project = ProjectService(session, settings, config).get_or_register(path)
            record = analyze_asset(session, project, clip, get_provider(settings, config), config)
    except AppError as exc:
        raise _fail(exc) from exc
    a = record["analysis"]
    typer.echo(f"{a['summary']}\n")
    for s in a["scenes"]:
        typer.echo(f"  {s['start']:6.1f}s-{s['end']:6.1f}s  [{s['interest']}/5] {s['description']}")
    typer.echo(f"\nSaved to data/analysis/{record['clip_id']}.json in the project.")


@app.command()
def serve(
    host: str = typer.Option(None, help="Override APP_HOST."),
    port: int = typer.Option(None, help="Override APP_PORT."),
    reload: bool = typer.Option(False, help="Auto-reload (development)."),
    allow_non_localhost: bool = typer.Option(
        False, "--allow-non-localhost", help="Permit binding to a non-loopback address (unsafe)."
    ),
) -> None:
    """Start the API server (localhost only by default)."""
    import uvicorn

    settings = get_settings()
    bind_host, bind_port = host or settings.app_host, port or settings.app_port
    if bind_host not in {"127.0.0.1", "localhost", "::1"} and not allow_non_localhost:
        typer.secho(
            f"Refusing to bind to {bind_host}: the API has no authentication and exposes your "
            "projects. Use 127.0.0.1, or pass --allow-non-localhost if you accept the risk.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
    setup_logging(get_app_config().logging.level, expand(get_app_config().logging.directory))
    typer.echo(f"API on http://{bind_host}:{bind_port}  (docs: /docs)")
    uvicorn.run("app.main:create_app", factory=True, host=bind_host, port=bind_port, reload=reload)


if __name__ == "__main__":
    app()
