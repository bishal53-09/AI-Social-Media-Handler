"""Documented extension points for stages that are not implemented yet.

Each class declares the stage contract (name, intended inputs/outputs) so the
orchestrator, configuration and docs already know about it. ``implemented`` is
``False``: the orchestrator refuses to run them instead of reporting fake
success. See docs/pipeline.md and docs/roadmap.md.
"""

from __future__ import annotations

from app.core.exceptions import UnsupportedOperationError
from app.pipeline.base import Stage, StageContext, StageResult


class _NotImplementedStage(Stage):
    implemented = False
    phase: str = ""
    description: str = ""

    def run(self, ctx: StageContext) -> StageResult:
        raise UnsupportedOperationError(
            f"Stage '{self.name}' is not implemented yet ({self.phase}). {self.description}"
        )


class ColorGradingStage(_NotImplementedStage):
    """TODO(phase 3): apply a LUT / colour transform.

    Inputs: a stitched video plus a colour profile that distinguishes the
    camera-original profile, the stitched colour space, the LUT input space and
    the output space (docs/pipeline.md). Output: ``media/processed/color-graded/``.
    The camera-specific transform stays configurable until verified.
    """

    name = "color_grading"
    phase = "Phase 3"
    description = "Camera-specific colour transforms are not verified for the Osmo 360 II."


class ReframingStage(_NotImplementedStage):
    """TODO(phase 3): reframe equirectangular video to 9:16, 16:9 or 1:1.

    Input: stitched equirectangular video + keyframed yaw/pitch/fov. Output:
    ``media/processed/reframed/`` (planned: ffmpeg ``v360`` filter).
    """

    name = "reframing"
    phase = "Phase 3"
    description = "Equirectangular reframing with keyframed camera movement is planned."


class EditingStage(_NotImplementedStage):
    """TODO(phase 4): cut and assemble segments from a validated edit plan."""

    name = "editing"
    phase = "Phase 4"
    description = "Executes validated edit plans deterministically; AI never runs commands."


class SubtitlesStage(_NotImplementedStage):
    """TODO(phase 4): transcription, caption timing and burn-in/sidecar subtitles."""

    name = "subtitles"
    phase = "Phase 4"
    description = "Caption generation and subtitle rendering are planned."


class RenderingStage(_NotImplementedStage):
    """TODO(phase 4): render platform-specific exports from ``export-presets.yaml``."""

    name = "rendering"
    phase = "Phase 4"
    description = "Platform export rendering is planned."


class AudioStage(_NotImplementedStage):
    """TODO(phase 4): loudness normalisation, music ducking, voice-over mixing."""

    name = "audio"
    phase = "Phase 4"
    description = "Audio processing is planned."


class AnalysisStage(_NotImplementedStage):
    """TODO(phase 4): run AI footage analysis as a pipeline stage.

    Today analysis is an explicit, on-demand workflow (``python -m app.cli
    analyze``; ``app.services.analysis_service``) because it sends sampled
    frames to an AI provider and therefore needs consent each time. Making it a
    stage means resolving how consent is granted for batch jobs.
    """

    name = "analysis"
    phase = "Phase 4"
    description = "Use `python -m app.cli analyze` for on-demand analysis."
