"""Shared helpers for paginated, searchable, sortable list queries."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from typing import Any, Literal

from sqlalchemy import Select
from sqlalchemy.orm import InstrumentedAttribute

SortOrder = Literal["asc", "desc"]


def like_pattern(text: str) -> str:
    """Case-insensitive substring pattern with LIKE wildcards in the input escaped (use ``escape='\\'``)."""
    escaped = text.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def apply_sort(
    q: Select[Any],
    columns: dict[str, InstrumentedAttribute[Any]],
    sort: str | None,
    order: SortOrder,
    default: list[Any],
    tiebreak: InstrumentedAttribute[Any],
) -> Select[Any]:
    """Order by a whitelisted column (``sort``) or the ``default`` ordering; ``tiebreak`` keeps paging stable."""
    column = columns.get(sort) if sort else None
    if column is None:
        return q.order_by(*default, tiebreak)
    return q.order_by(column.desc() if order == "desc" else column.asc(), tiebreak)


def day_start(d: date) -> datetime:
    return datetime.combine(d, time.min, tzinfo=UTC)


def day_end_exclusive(d: date) -> datetime:
    return day_start(d) + timedelta(days=1)
