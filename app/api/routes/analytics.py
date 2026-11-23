from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import ContentPostServiceDep
from app.schemas.engagement import AnalyticsOverview

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/overview", response_model=AnalyticsOverview)
def overview(
    svc: ContentPostServiceDep, project_id: str | None = None, top: int = Query(default=10, ge=1, le=50)
) -> AnalyticsOverview:
    """Rollup of the most recent stored metrics. Posts never synced have no data and are counted separately."""
    return svc.analytics_overview(project_id, top)
