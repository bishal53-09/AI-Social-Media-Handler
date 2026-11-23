from __future__ import annotations

import sys

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from app import __version__
from app.api.deps import SessionDep
from app.pipeline.ffmpeg import check_binary

router = APIRouter(tags=["health"])


class Health(BaseModel):
    status: str
    version: str
    database: str
    ffmpeg: bool
    ffprobe: bool
    python: str


@router.get("/health", response_model=Health)
def health(session: SessionDep) -> Health:
    try:
        session.execute(text("SELECT 1"))
        db = "ok"
    except Exception:
        db = "error"
    return Health(
        status="ok" if db == "ok" else "degraded",
        version=__version__,
        database=db,
        ffmpeg=check_binary("ffmpeg") is not None,
        ffprobe=check_binary("ffprobe") is not None,
        python=sys.version.split()[0],
    )
