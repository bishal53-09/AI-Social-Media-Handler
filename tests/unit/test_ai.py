from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import anthropic
import httpx
import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.ai.anthropic_provider import FALLBACK_BETA, AnthropicProvider
from app.ai.base import AIProvider, ImagePart, Part, T, TextPart, enforce_media_consent
from app.ai.caption_generator import CaptionGenerator
from app.ai.edit_planner import EditPlanner
from app.ai.footage_analyzer import FootageAnalyzer, describe_clip
from app.ai.frames import SampledFrame, sample_frames, sample_timestamps
from app.ai.highlight_detector import HighlightDetector
from app.ai.prompts import load_prompt
from app.ai.registry import get_provider
from app.ai.schemas import (
    CaptionSet,
    EditPlan,
    FootageAnalysis,
    Highlight,
    HighlightList,
    PlanSegment,
    ReframeView,
    Scene,
)
from app.ai.validation import validate_edit_plan
from app.core.config import AnthropicConfig, AppConfig, EditPlanConfig, MediaTransmissionConfig, Settings
from app.core.exceptions import AIResponseError, ConfigurationError, ConsentRequiredError
from tests.conftest import make_video, needs_ffmpeg


class FakeProvider(AIProvider):
    """Returns canned responses and records what it was sent."""

    name = "fake"

    def __init__(self, *responses: Any) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, Sequence[Part]]] = []

    def generate(
        self, *, system: str, parts: Sequence[Part], response_model: type[T], max_tokens: int | None = None
    ) -> T:
        self.calls.append((system, parts))
        return self.responses.pop(0)  # type: ignore[no-any-return]


def plan(*segments: PlanSegment, fmt: str = "9:16", target: float = 10) -> EditPlan:
    return EditPlan(format=fmt, duration_target=target, segments=list(segments))  # type: ignore[arg-type]


def seg(source: str = "clip_a", start: float = 0, end: float = 5, **kw: Any) -> PlanSegment:
    return PlanSegment(source=source, start=start, end=end, **kw)


LIMITS = EditPlanConfig()


# --- schema strictness ---------------------------------------------------------------


def test_spec_edit_plan_example_parses() -> None:
    p = EditPlan.model_validate(
        {
            "format": "9:16",
            "duration_target": 35,
            "segments": [
                {"source": "clip_001.mp4", "start": 12.5, "end": 16.0, "reframe": {"yaw": 35, "pitch": -5, "fov": 85}}
            ],
        }
    )
    assert p.segments[0].reframe == ReframeView(yaw=35, pitch=-5, fov=85)


@pytest.mark.parametrize("extra", [{"command": "rm -rf /"}, {"ffmpeg_args": ["-i", "x"]}, {"shell": "ls"}])
def test_unknown_fields_such_as_commands_are_rejected(extra: dict[str, Any]) -> None:
    base = {"format": "9:16", "duration_target": 10, "segments": [{"source": "a", "start": 0, "end": 1}]}
    with pytest.raises(ValidationError):
        EditPlan.model_validate({**base, **extra})
    with pytest.raises(ValidationError):
        EditPlan.model_validate({**base, "segments": [{"source": "a", "start": 0, "end": 1, **extra}]})


@pytest.mark.parametrize(
    "bad",
    [
        {"format": "4:3"},
        {"duration_target": 0},
        {"segments": []},
        {"segments": [{"source": "a", "start": -1, "end": 1}]},
        {"segments": [{"source": "a", "start": 0, "end": float("inf")}]},
        {"segments": [{"source": "a", "start": 0, "end": 1, "reframe": {"yaw": 400, "pitch": 0, "fov": 90}}]},
        {"segments": [{"source": "a", "start": 0, "end": 1, "reframe": {"yaw": 0, "pitch": 0, "fov": 5}}]},
    ],
)
def test_invalid_plans_are_rejected(bad: dict[str, Any]) -> None:
    base = {"format": "9:16", "duration_target": 10, "segments": [{"source": "a", "start": 0, "end": 1}]}
    with pytest.raises(ValidationError):
        EditPlan.model_validate({**base, **bad})


def test_caption_hashtags_are_sanitised() -> None:
    c = CaptionSet(caption="x", hashtags=["#Travel", "travel", "no spaces!", "#", "ok_1"])
    assert c.hashtags == ["Travel", "nospaces", "ok_1"]


# --- semantic validation ---------------------------------------------------------------


def test_valid_plan_passes_and_returns_warnings_only() -> None:
    warnings = validate_edit_plan(plan(seg(end=5), seg("clip_b", 1, 6)), {"clip_a": 10.0, "clip_b": 10.0}, LIMITS)
    assert warnings == []
    assert validate_edit_plan(plan(seg(end=2), target=30), {"clip_a": 10.0}, LIMITS)  # >25% off target


@pytest.mark.parametrize(
    ("p", "needle"),
    [
        (plan(seg("../../etc/passwd")), "unknown source"),
        (plan(seg("clip_zzz")), "unknown source"),
        (plan(seg(start=5, end=5)), "end must be after start"),
        (plan(seg(end=99)), "is 10.0s long"),
        (plan(*[seg(end=1)] * 61), "segments exceeds"),
        (plan(seg(end=9), seg(end=9), seg(end=9), seg(end=9)), "exceeds"),  # replaced below
    ],
)
def test_unsafe_plans_are_rejected(p: EditPlan, needle: str) -> None:
    limits = LIMITS.model_copy(update={"max_duration_seconds": 30})
    if needle == "exceeds":
        needle = "total duration"
    with pytest.raises(AIResponseError) as exc:
        validate_edit_plan(p, {"clip_a": 10.0}, limits)
    assert needle in json.dumps(exc.value.details)


def test_fov_limits_come_from_config() -> None:
    p = plan(seg(reframe=ReframeView(yaw=0, pitch=0, fov=110)))
    validate_edit_plan(p, {"clip_a": 10.0}, LIMITS)
    with pytest.raises(AIResponseError, match="failed validation"):
        validate_edit_plan(p, {"clip_a": 10.0}, EditPlanConfig(fov_range=(40, 100)))


# --- consent and transmission --------------------------------------------------------------


def test_images_are_blocked_without_consent() -> None:
    policy = MediaTransmissionConfig()  # allow_frames defaults to False
    with pytest.raises(ConsentRequiredError, match="allow_frames"):
        enforce_media_consent([TextPart("hi"), ImagePart(b"x")], policy)
    enforce_media_consent([TextPart("text only")], policy)  # text never needs consent
    ok = MediaTransmissionConfig(allow_frames=True, max_frames_per_clip=2)
    enforce_media_consent([ImagePart(b"x")] * 2, ok)
    with pytest.raises(ConsentRequiredError, match="limit"):
        enforce_media_consent([ImagePart(b"x")] * 3, ok)


def test_clip_description_contains_no_paths_or_filenames() -> None:
    text = describe_clip("clip_1", {"duration": 10, "width": 100, "height": 50, "fps": 30}, "flat")
    assert "clip_1" in text and "/" not in text and ".mp4" not in text


def test_analyzer_sends_labelled_frames_and_validates_scene_times() -> None:
    good = FootageAnalysis(summary="s", scenes=[Scene(start=0, end=4, description="d", interest=3)])
    prov = FakeProvider(good)
    frames = [SampledFrame(1.0, b"jpg1"), SampledFrame(3.0, b"jpg2")]
    out = FootageAnalyzer(prov).analyze("clip_1", {"duration": 5.0}, "flat", frames)
    assert out is good
    parts = prov.calls[0][1]
    assert sum(isinstance(p, ImagePart) for p in parts) == 2
    assert any(isinstance(p, TextPart) and "Frame at 3.0s" in p.text for p in parts)

    bad = FootageAnalysis(summary="s", scenes=[Scene(start=0, end=99, description="d", interest=3)])
    with pytest.raises(AIResponseError, match="analysis failed"):
        FootageAnalyzer(FakeProvider(bad)).analyze("c", {"duration": 5.0}, "flat", frames)


def test_highlights_are_text_only_validated_and_ranked() -> None:
    hl = HighlightList(
        highlights=[
            Highlight(clip_id="c1", start=0, end=3, score=0.4, title="a", reason="r"),
            Highlight(clip_id="c1", start=4, end=8, score=0.9, title="b", reason="r"),
        ]
    )
    prov = FakeProvider(hl)
    analysis = FootageAnalysis(summary="s", scenes=[])
    out = HighlightDetector(prov).detect({"c1": analysis}, {"c1": 10.0}, max_highlights=1)
    assert [h.title for h in out.highlights] == ["b"]
    assert not any(isinstance(p, ImagePart) for p in prov.calls[0][1])  # no media

    ghost = HighlightList(highlights=[Highlight(clip_id="nope", start=0, end=1, score=1, title="t", reason="r")])
    with pytest.raises(AIResponseError) as exc:
        HighlightDetector(FakeProvider(ghost)).detect({}, {"c1": 10.0})
    assert "unknown clip" in json.dumps(exc.value.details)


def test_planner_returns_plan_or_rejects() -> None:
    hl = HighlightList(highlights=[])
    ok = plan(seg(end=5), target=5)
    result, warnings = EditPlanner(FakeProvider(ok), LIMITS).plan(hl, {"clip_a": 10.0})
    assert result is ok and warnings == []
    with pytest.raises(AIResponseError):
        EditPlanner(FakeProvider(plan(seg("hacked.mp4"))), LIMITS).plan(hl, {"clip_a": 10.0})


def test_caption_generator_enforces_limits() -> None:
    raw = CaptionSet(caption="x" * 3000, hashtags=[f"t{i}" for i in range(20)])
    out = CaptionGenerator(FakeProvider(raw)).generate("instagram", "summary", max_hashtags=5)
    assert len(out.caption) == 2200 and len(out.hashtags) == 5


def test_prompts_load_and_reject_traversal() -> None:
    for name in ("footage_analysis", "highlights", "edit_plan", "captions"):
        assert len(load_prompt(name)) > 100
    with pytest.raises(FileNotFoundError):
        load_prompt("../schemas")


# --- frame sampling ----------------------------------------------------------------------------


def test_timestamps_are_evenly_spread() -> None:
    assert sample_timestamps(10, 4) == [1.25, 3.75, 6.25, 8.75]
    assert sample_timestamps(0, 4) == [0.0]


@needs_ffmpeg
def test_frames_are_downscaled_jpegs_without_metadata(tmp_path: Path) -> None:
    from io import BytesIO

    from PIL import Image

    video = make_video(tmp_path / "v.mp4", size="1280x640", seconds=3)
    policy = MediaTransmissionConfig(max_frames_per_clip=3, frame_width=320)
    frames = sample_frames(video, 3.0, policy)
    assert len(frames) == 3
    for f in frames:
        with Image.open(BytesIO(f.jpeg)) as im:
            assert im.format == "JPEG" and im.width == 320 and not im.getexif()


# --- Anthropic provider (no network: fake client) ---------------------------------------------------


class FakeMessages:
    def __init__(self, result: Any = None, exc: Exception | None = None) -> None:
        self.result, self.exc, self.kwargs = result, exc, {}

    def parse(self, **kwargs: Any) -> Any:
        self.kwargs = kwargs
        if self.exc:
            raise self.exc
        return self.result


class FakeClient:
    def __init__(self, messages: FakeMessages) -> None:
        self.beta = type("Beta", (), {"messages": messages})()


class Resp:
    def __init__(self, parsed: Any = None, stop: str = "end_turn") -> None:
        self.parsed_output, self.stop_reason, self.stop_details = parsed, stop, None


def provider(msgs: FakeMessages, allow: bool = True, **cfg: Any) -> AnthropicProvider:
    return AnthropicProvider(
        None, AnthropicConfig(**cfg), MediaTransmissionConfig(allow_frames=allow), client=FakeClient(msgs)
    )


def test_provider_sends_structured_request_with_default_model_and_fallbacks() -> None:
    cap = CaptionSet(caption="hi")
    msgs = FakeMessages(Resp(cap))
    out = provider(msgs).generate(
        system="sys", parts=[TextPart("t"), ImagePart(b"\xff\xd8")], response_model=CaptionSet
    )
    assert out is cap
    kw = msgs.kwargs
    assert kw["model"] == "claude-opus-5-5" and kw["output_format"] is CaptionSet
    assert kw["thinking"] == {"type": "adaptive"} and kw["output_config"] == {"effort": "high"}
    assert kw["betas"] == [FALLBACK_BETA] and kw["fallbacks"] == "default"
    content = kw["messages"][0]["content"]
    assert content[0] == {"type": "text", "text": "t"}
    assert content[1]["source"]["type"] == "base64" and content[1]["source"]["media_type"] == "image/jpeg"
    assert "temperature" not in kw  # removed on current models


def test_fallbacks_can_be_disabled() -> None:
    msgs = FakeMessages(Resp(CaptionSet(caption="x")))
    provider(msgs, server_side_fallbacks=False).generate(system="s", parts=[], response_model=CaptionSet)
    assert "fallbacks" not in msgs.kwargs and "betas" not in msgs.kwargs


def test_provider_blocks_frames_without_consent_before_any_request() -> None:
    msgs = FakeMessages(Resp(CaptionSet(caption="x")))
    with pytest.raises(ConsentRequiredError):
        provider(msgs, allow=False).generate(system="s", parts=[ImagePart(b"x")], response_model=CaptionSet)
    assert msgs.kwargs == {}  # never reached the SDK


@pytest.mark.parametrize(
    ("resp", "needle"),
    [
        (Resp(None, "refusal"), "declined"),
        (Resp(None, "max_tokens"), "cut off"),
        (Resp(None), "no valid structured output"),
    ],
)
def test_provider_error_paths(resp: Resp, needle: str) -> None:
    with pytest.raises(AIResponseError, match=needle):
        provider(FakeMessages(resp)).generate(system="s", parts=[], response_model=CaptionSet)


def _status_error(cls: type[anthropic.APIStatusError], code: int) -> anthropic.APIStatusError:
    req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    return cls("boom sk-ant-secretsecret1234", response=httpx.Response(code, request=req), body=None)


def test_provider_translates_sdk_errors_without_leaking_secrets() -> None:
    cases = [
        (_status_error(anthropic.AuthenticationError, 401), "key was rejected"),
        (_status_error(anthropic.RateLimitError, 429), "rate limit"),
        (_status_error(anthropic.BadRequestError, 400), "rejected the request"),
        (_status_error(anthropic.InternalServerError, 500), "API error"),
        (anthropic.APIConnectionError(request=httpx.Request("POST", "https://x")), "Could not reach"),
    ]
    for exc, needle in cases:
        with pytest.raises(AIResponseError, match=needle) as info:
            provider(FakeMessages(exc=exc)).generate(system="s", parts=[], response_model=CaptionSet)
        assert "secretsecret" not in info.value.message


def test_missing_api_key_gives_actionable_error() -> None:
    with pytest.raises(ConfigurationError, match="ANTHROPIC_API_KEY"):
        AnthropicProvider(None, AnthropicConfig(), MediaTransmissionConfig())


def test_registry_builds_anthropic_provider_and_rejects_unknown(config: AppConfig) -> None:
    s = Settings(_env_file=None, anthropic_api_key="sk-ant-test-key-123456")  # type: ignore[call-arg]
    assert get_provider(s, config).name == "anthropic"
    cfg = config.model_copy(deep=True)
    cfg.ai.provider = "skynet"
    with pytest.raises(ConfigurationError, match="Unknown AI provider"):
        get_provider(s, cfg)


# --- end-to-end analysis workflow with a fake provider -----------------------------------------------


@needs_ffmpeg
def test_analysis_workflow_writes_validated_json_only_with_consent(
    session: Session, settings: Settings, config: AppConfig
) -> None:
    from app.services.analysis_service import analyze_asset
    from app.services.media_service import MediaService
    from app.services.project_service import ProjectService

    project = ProjectService(session, settings, config).init_project("AI Test")
    make_video(Path(project.path) / "media/raw/2026-11-23/c.mp4", seconds=3)
    MediaService(session, config).scan(project)

    answer = FootageAnalysis(summary="A test pattern.", scenes=[Scene(start=0, end=2, description="d", interest=2)])
    prov = FakeProvider(answer)
    with pytest.raises(ConsentRequiredError):  # default config: no consent
        analyze_asset(session, project, "media/raw/2026-11-23/c.mp4", prov, config)
    assert prov.calls == []

    config.ai.media_transmission.allow_frames = True
    config.ai.media_transmission.max_frames_per_clip = 3
    record = analyze_asset(session, project, "media/raw/2026-11-23/c.mp4", prov, config)
    saved = json.loads((Path(project.path) / f"data/analysis/{record['clip_id']}.json").read_text())
    assert saved["analysis"]["summary"] == "A test pattern." and len(saved["frames_sent"]) == 3
    assert sum(isinstance(p, ImagePart) for p in prov.calls[0][1]) == 3
    assert saved["source"] == "media/raw/2026-11-23/c.mp4"
