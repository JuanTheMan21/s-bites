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

from core import Tier
from core.block_types import BlockType
from interfaces import CompositionInvalid
from rendering.render_segment import render_segment
from tests.fakes import FakeRenderBackend
from tests.segment_examples import an_authored_segment

DURATION_MS = 21_000

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is not on PATH")


@pytest.mark.parametrize(
    "missing_field", ["duration_ms", "tier", "scene"], ids=lambda f: f"missing_{f}"
)
async def test_a_segment_missing_a_required_field_raises_value_error(
    tmp_path, missing_field: str
) -> None:
    segment = an_authored_segment(
        0, BlockType.TITLE, Tier.STATIC, duration_ms=DURATION_MS
    ).model_copy(update={missing_field: None})
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
    segment = an_authored_segment(0, BlockType.TEXT_PANEL, Tier.ANIMATED, duration_ms=DURATION_MS)
    render = FakeRenderBackend(findings=["[error] fake_finding: something is wrong"])

    with pytest.raises(CompositionInvalid, match="fake_finding"):
        await render_segment(
            segment, render, composition_dir=tmp_path / "comp", dest=tmp_path / "clip.mp4", fps=24
        )

    assert render.captures == []
    assert render.renders == []


async def test_a_geometry_finding_raises_composition_invalid_before_any_capture_or_render(
    tmp_path,
) -> None:
    """T18H's second gate, the same "invalid compositions are caught before rendering" contract
    lint already holds -- this one for a defect lint structurally cannot see (real overlap)."""
    segment = an_authored_segment(0, BlockType.TEXT_PANEL, Tier.ANIMATED, duration_ms=DURATION_MS)
    render = FakeRenderBackend(
        geometry_findings=["[error] content_overlap: two text blocks overlap"]
    )

    with pytest.raises(CompositionInvalid, match="content_overlap"):
        await render_segment(
            segment, render, composition_dir=tmp_path / "comp", dest=tmp_path / "clip.mp4", fps=24
        )

    assert render.captures == []
    assert render.renders == []


async def test_a_geometry_warning_does_not_block_the_render(tmp_path) -> None:
    segment = an_authored_segment(0, BlockType.STAT_CALLOUT, Tier.ANIMATED, duration_ms=DURATION_MS)
    render = FakeRenderBackend(geometry_findings=["[warning] sweep_static: nothing moved"])
    dest = tmp_path / "clip.mp4"

    result = await render_segment(
        segment, render, composition_dir=tmp_path / "comp", dest=dest, fps=24
    )

    assert result == dest
    assert len(render.renders) == 1


async def test_a_lint_warning_does_not_block_the_render(tmp_path) -> None:
    """T18A: found live -- a real render tripped hyperframes' own [warning]
    composition_file_too_large once captions pushed a template past its line-count nag, and
    treating every finding as fatal (D2's original stance) blocked every real render permanently.
    Only [error] severity is fatal now; a [warning] finding must not stop the render.
    """
    segment = an_authored_segment(0, BlockType.STAT_CALLOUT, Tier.ANIMATED, duration_ms=DURATION_MS)
    render = FakeRenderBackend(findings=["[warning] composition_file_too_large: 315 lines"])
    dest = tmp_path / "clip.mp4"

    result = await render_segment(
        segment, render, composition_dir=tmp_path / "comp", dest=dest, fps=24
    )

    assert result == dest
    assert len(render.renders) == 1


async def test_tier_animated_dispatches_to_render_backend_render(tmp_path) -> None:
    segment = an_authored_segment(0, BlockType.STAT_CALLOUT, Tier.ANIMATED, duration_ms=DURATION_MS)
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
    segment = an_authored_segment(0, BlockType.CODE_PANEL, Tier.STATIC, duration_ms=DURATION_MS)
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
async def test_tier_reveal_captures_at_planned_instants_past_the_entrance_settle(tmp_path) -> None:
    """T18K/D161: Tier 1 no longer samples 4 fixed, evenly-spaced instants blind to the segment's
    own cues and reveal timing -- it samples ``rendering/still_plan.py``'s plan instead (every
    caption-cue start plus every block's reveal candidate). This segment's narration ("Narration.")
    synthesizes into one cue via ``mux.caption_cues.cues_for_segment``'s fallback, and its
    GRAPH_DIAGRAM block contributes its own entrance/item candidates -- still, not evenly spaced,
    but always starting past entrance-settle and ending at the segment's full duration."""
    segment = an_authored_segment(0, BlockType.GRAPH_DIAGRAM, Tier.REVEAL, duration_ms=DURATION_MS)
    render = FakeRenderBackend()
    dest = tmp_path / "clip.mp4"

    result = await render_segment(
        segment, render, composition_dir=tmp_path / "comp", dest=dest, fps=24
    )

    assert result == dest
    assert dest.exists() and dest.stat().st_size > 0
    assert len(render.captures) == 1
    at_seconds = render.captures[0].at_seconds
    assert len(at_seconds) >= 2
    assert at_seconds[0] == pytest.approx(1.5)  # SETTLE_S_CAP, since DURATION_MS * 0.12 > 1.5
    assert at_seconds[-1] == pytest.approx(DURATION_MS / 1000)
    assert list(at_seconds) == sorted(at_seconds)
    assert render.renders == []


@needs_ffmpeg
async def test_tier_reveal_captures_at_least_one_still_per_caption_cue(tmp_path) -> None:
    """T18K/D161: the actual user-facing bug. Before this fix, a segment with 9 caption cues
    could only ever show 4 of them (``REVEAL_STATE_COUNT``) -- 9 cues here must yield at least
    9 stills, one per cue boundary, not a fixed 4 regardless of caption density."""
    from interfaces.tts_provider import WordMark

    duration_ms = 27_660
    words = [f"word{i}" for i in range(65)]  # ceil(65 / MAX_WORDS_PER_CUE=8) == 9 cues
    slot_ms = duration_ms / len(words)
    word_marks = [
        WordMark(text=word, offset_ms=round(i * slot_ms), duration_ms=round(slot_ms))
        for i, word in enumerate(words)
    ]
    segment = an_authored_segment(
        0, BlockType.TEXT_PANEL, Tier.REVEAL, duration_ms=duration_ms
    ).model_copy(update={"word_marks": word_marks, "narration": " ".join(words)})
    render = FakeRenderBackend()
    dest = tmp_path / "clip.mp4"

    await render_segment(segment, render, composition_dir=tmp_path / "comp", dest=dest, fps=24)

    at_seconds = render.captures[0].at_seconds
    assert len(at_seconds) >= 9
