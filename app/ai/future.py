"""Documented extension points for AI modules that are not built yet.

They exist so configuration, docs and call sites have a stable name to refer
to. They raise ``UnsupportedOperationError`` rather than return placeholder
data. See docs/ai-workflow.md and docs/roadmap.md.
"""

from __future__ import annotations

from typing import Any

from app.core.exceptions import UnsupportedOperationError


class ReframePlanner:
    """TODO(phase 3/4): turn a scene analysis into keyframed yaw/pitch/fov paths.

    Output must be validated like ``EditPlan`` (finite numbers, fov limits) and is
    executed by the deterministic reframing stage — never by the model.
    """

    def plan(self, *_args: Any, **_kwargs: Any) -> None:
        raise UnsupportedOperationError("ReframePlanner is not implemented yet (Phase 3/4).")


class TrendResearcher:
    """TODO(phase 4+): research platform trends into ``data/trends/``.

    Must use official sources or explicit user-provided notes
    (``media/references/trend-notes``); no scraping of platforms that forbid it.
    """

    def research(self, *_args: Any, **_kwargs: Any) -> None:
        raise UnsupportedOperationError("TrendResearcher is not implemented yet (Phase 4+).")
