"""``rendering/render_segment.py`` -- offline against ``FakeRenderBackend``.

Tier 0/1's dispatch tests below do run real ffmpeg (``mux/frames_to_clip.py`` shells out to it
directly, with no fake to substitute -- the same reasoning ``FakeRenderBackend``'s own module
docstring gives for why it cannot fake a real MP4). ffmpeg is a local, no-network binary this
project's environment guarantees, the same bargain ``test_audio_duration.py`` makes for ffprobe,
so these stay in the default offline suite rather than behind ``live``/``local_live`` -- both of
which are reserved for a real network backend or a real browser/CLI, neither of which applies here.
"""

import shutil

import pytest

from core import Segment, Tier, VisualIntent
from interfaces import CompositionInvalid
from rendering.render_segment import render_segment
from tests.fakes import FakeRenderBackend
from tests.segment_examples import a_segment
from tests.slot_examples import EXAMPLES

DURATION_MS = 21_000

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is not on PATH")


def _authored_segment(intent: VisualIntent, tier: Tier) -> Segment:
    return a_segment(0, intent=intent, duration_ms=DURATION_MS).model_copy(
        update={"tier": tier, "slots": EXAMPLES[intent]}
    )


@pytest.mark.parametrize(
    "missing_field", ["duration_ms", "tier", "slots"], ids=lambda f: f"missing_{f}"
)
async def test_a_segment_missing_a_required_field_raises_value_error(
    tmp_path, missing_field: str
) -> None:
    segment = _authored_segment(VisualIntent.TITLE_CARD, Tier.STATIC).model_copy(
        update={missing_field: None}
    )
    render = FakeRenderBackend()

    with pytest.raises(ValueError, match=missing_field):
        await render_segment(
            segment, render, composition_dir=tmp_path / "comp", dest=tmp_path / "clip.mp4", fps=24
        )

    assert render.captures == []
    assert render.renders == []


async def test_a_lint_finding_raises_composition_invalid_before_any_capture_or_render(
    tmp_path,
) -> None:
    """The "invalid compositions are caught before rendering" half of T17's DoD."""
    segment = _authored_segment(VisualIntent.BULLET_LIST, Tier.ANIMATED)
    render = FakeRenderBackend(findings=["[error] fake_finding: something is wrong"])

    with pytest.raises(CompositionInvalid, match="fake_finding"):
        await render_segment(
            segment, render, composition_dir=tmp_path / "comp", dest=tmp_path / "clip.mp4", fps=24
        )

    assert render.captures == []
    assert render.renders == []


async def test_a_lint_warning_does_not_block_the_render(tmp_path) -> None:
    """T18A: found live -- a real render tripped hyperframes' own [warning]
    composition_file_too_large once captions pushed a template past its line-count nag, and
    treating every finding as fatal (D2's original stance) blocked every real render permanently.
    Only [error] severity is fatal now; a [warning] finding must not stop the render.
    """
    segment = _authored_segment(VisualIntent.STAT_CALLOUT, Tier.ANIMATED)
    render = FakeRenderBackend(findings=["[warning] composition_file_too_large: 315 lines"])
    dest = tmp_path / "clip.mp4"

    result = await render_segment(
        segment, render, composition_dir=tmp_path / "comp", dest=dest, fps=24
    )

    assert result == dest
    assert len(render.renders) == 1


async def test_tier_animated_dispatches_to_render_backend_render(tmp_path) -> None:
    segment = _authored_segment(VisualIntent.STAT_CALLOUT, Tier.ANIMATED)
    render = FakeRenderBackend()
    dest = tmp_path / "clip.mp4"

    result = await render_segment(
        segment, render, composition_dir=tmp_path / "comp", dest=dest, fps=24
    )

    assert result == dest
    assert render.captures == []
    assert len(render.renders) == 1
    assert render.renders[0].duration_ms == DURATION_MS


@needs_ffmpeg
async def test_tier_static_captures_one_timestamp_at_the_end_of_the_composition(tmp_path) -> None:
    segment = _authored_segment(VisualIntent.CODE_WALKTHROUGH, Tier.STATIC)
    render = FakeRenderBackend()
    dest = tmp_path / "clip.mp4"

    result = await render_segment(
        segment, render, composition_dir=tmp_path / "comp", dest=dest, fps=24
    )

    assert result == dest
    assert dest.exists() and dest.stat().st_size > 0
    assert len(render.captures) == 1
    assert render.captures[0].at_seconds == (DURATION_MS / 1000,)
    assert render.renders == []


@needs_ffmpeg
async def test_tier_reveal_captures_four_timestamps_past_the_entrance_settle(tmp_path) -> None:
    """Not evenly spaced from t=0 -- the first sample must land after entrance has settled, not
    at the pre-animation blank frame (the bug a real render surfaced)."""
    segment = _authored_segment(VisualIntent.DIAGRAM_FLOW, Tier.REVEAL)
    render = FakeRenderBackend()
    dest = tmp_path / "clip.mp4"

    result = await render_segment(
        segment, render, composition_dir=tmp_path / "comp", dest=dest, fps=24
    )

    assert result == dest
    assert dest.exists() and dest.stat().st_size > 0
    assert len(render.captures) == 1
    at_seconds = render.captures[0].at_seconds
    assert len(at_seconds) == 4
    assert at_seconds[0] == pytest.approx(1.5)  # SETTLE_S_CAP, since DURATION_MS * 0.12 > 1.5
    assert at_seconds[-1] == pytest.approx(DURATION_MS / 1000)
    assert render.renders == []
