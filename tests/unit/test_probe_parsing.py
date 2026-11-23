"""ffprobe JSON → ProbeResult, without needing ffmpeg."""

from __future__ import annotations

from typing import Any

import pytest

from app.pipeline.ffmpeg import parse_probe, parse_progress_line
from app.pipeline.stages.probe import classify_media


def probe_json(**video: Any) -> dict[str, Any]:
    v = {
        "codec_type": "video",
        "codec_name": "hevc",
        "width": 3840,
        "height": 1920,
        "avg_frame_rate": "30000/1001",
        "pix_fmt": "yuv420p10le",
        "color_space": "bt2020nc",
        "color_transfer": "arib-std-b67",
        "color_primaries": "bt2020",
    }
    v.update(video)
    return {
        "format": {
            "format_name": "mov,mp4",
            "duration": "12.5",
            "size": "1000",
            "bit_rate": "640",
            "tags": {"creation_time": "2026-11-23T10:00:00Z"},
        },
        "streams": [v, {"codec_type": "audio", "codec_name": "aac"}],
    }


def test_basic_fields_and_colour_metadata() -> None:
    p = parse_probe(probe_json())
    assert (p.width, p.height) == (3840, 1920)
    assert p.fps == 29.97
    assert p.duration == 12.5 and p.video_codec == "hevc" and p.audio_codec == "aac"
    assert (p.color_space, p.color_transfer, p.color_primaries) == ("bt2020nc", "arib-std-b67", "bt2020")
    assert p.has_audio and p.video_stream_count == 1


def test_two_to_one_without_metadata_is_only_flagged_as_possible_360() -> None:
    p = parse_probe(probe_json())
    assert not p.is_equirectangular and p.projection is None and p.projection_source is None
    assert p.possible_360 and p.to_dict()["possible_360"] is True
    assert p.warnings and "media/stitched/" in p.warnings[0]


def test_two_to_one_counts_as_360_only_inside_the_stitched_folder() -> None:
    p = parse_probe(probe_json())
    assert classify_media("media/raw/2026-11-23/wide.mp4", p) == "flat"
    assert classify_media("media/stitched/pano.mp4", p) == "360-stitched"


@pytest.mark.parametrize(
    ("rel", "size", "side_data"),
    [
        ("media/raw/phone.mov", (1080, 1920), []),  # vertical phone clip
        ("media/raw/phone-rotated.mp4", (1920, 1080), [{"rotation": -90}]),  # stored landscape, shown vertical
        ("media/raw/camera.mkv", (3840, 2160), []),
        ("media/raw/drone.MP4", (2720, 1530), []),
        ("media/raw/screen.webm", (1440, 900), []),
        ("media/raw/square.mp4", (1080, 1080), []),
        ("media/ready/final-edit.mp4", (1920, 1080), []),
    ],
)
def test_ordinary_video_from_any_source_is_flat(
    rel: str, size: tuple[int, int], side_data: list[dict[str, Any]]
) -> None:
    p = parse_probe(probe_json(width=size[0], height=size[1], side_data_list=side_data))
    assert classify_media(rel, p) == "flat"
    assert not p.is_equirectangular and not p.possible_360 and not p.warnings


def test_spherical_metadata_is_authoritative() -> None:
    p = parse_probe(
        probe_json(
            width=1920,
            height=1080,
            side_data_list=[{"side_data_type": "Spherical Mapping", "projection": "equirectangular"}],
        )
    )
    assert p.is_equirectangular and p.projection_source == "metadata"


def test_flat_video_is_not_360() -> None:
    p = parse_probe(probe_json(width=1920, height=1080))
    assert not p.is_equirectangular and p.projection is None


def test_rotation_swaps_dimensions() -> None:
    p = parse_probe(
        probe_json(width=1920, height=1080, side_data_list=[{"side_data_type": "Display Matrix", "rotation": -90}])
    )
    assert (p.width, p.height) == (1080, 1920) and p.rotation == 90


def test_multiple_video_streams_use_largest_and_are_counted() -> None:
    data = probe_json(width=1920, height=1920)
    data["streams"].insert(
        1, {"codec_type": "video", "codec_name": "hevc", "width": 3840, "height": 3840, "avg_frame_rate": "30/1"}
    )
    p = parse_probe(data)
    assert p.video_stream_count == 2 and p.width == 3840


def test_audio_only_file_warns() -> None:
    p = parse_probe({"format": {"duration": "1"}, "streams": [{"codec_type": "audio"}]})
    assert p.video_stream_count == 0 and p.warnings


def test_missing_values_do_not_crash() -> None:
    p = parse_probe({"format": {}, "streams": [{"codec_type": "video", "avg_frame_rate": "0/0"}]})
    assert p.fps is None and p.width is None


def test_classification() -> None:
    eq = parse_probe(probe_json())
    flat = parse_probe(probe_json(width=1920, height=1080))
    assert classify_media("media/raw/a.osv", flat) == "360"  # camera original container
    assert classify_media("media/stitched/a.mp4", eq) == "360-stitched"
    assert classify_media("media/raw/a.mp4", flat) == "flat"


def test_progress_line_parsing() -> None:
    assert parse_progress_line("out_time_us=1500000", 3.0) == 0.5
    assert parse_progress_line("out_time_ms=9000000", 3.0) == 1.0  # clamped
    assert parse_progress_line("frame=12", 3.0) is None
    assert parse_progress_line("out_time_us=1", None) is None
