"""``core/graph/nodes/render_scene.py``'s T18I recovery sequence: one bounded re-author for a
content-shaped geometry finding, a deterministic title-card fallback otherwise, both recorded on
``Segment.render_outcome`` -- and the resume-idempotency guard that skips a segment already
rendered. Offline, against ``FakeRenderBackend``/``FakeLLMProvider``, real ffmpeg (same split
``test_render_scene.py`` already makes).
"""

from pathlib import Path

from core.block_types import BlockType
from core.graph import GraphContext
from core.graph.nodes.render_scene import local_clip_path
from core.models import Tier
from tests.fakes import FakeLLMProvider, FakeRenderBackend, FakeStorage
from tests.fakes.tts_provider import FakeTTSProvider
from tests.scene_author_fixtures import a_payload_for, a_skill_registry, no_annotations
from tests.segment_examples import an_authored_segment
from tests.test_render_scene import (
    DURATION_MS,
    JOB_ID,
    _write_narration,
    needs_ffmpeg,
    run_render_scene,
)


def _context(
    tmp_path: Path, *, render: FakeRenderBackend, llm: FakeLLMProvider | None = None
) -> GraphContext:
    return GraphContext(
        llm=llm if llm is not None else FakeLLMProvider([]),
        tts=FakeTTSProvider(),
        storage=FakeStorage(),
        skills=a_skill_registry(),
        render=render,
        working_dir=tmp_path / "work",
        frame_budget=600,
        fps=24,
    )


@needs_ffmpeg
async def test_a_clean_first_attempt_has_no_render_outcome(tmp_path: Path) -> None:
    segment = an_authored_segment(0, BlockType.TEXT_PANEL, Tier.STATIC, duration_ms=DURATION_MS)
    render = FakeRenderBackend()
    context = _context(tmp_path, render=render)
    _write_narration(context.working_dir)

    result = await run_render_scene(segment, context)

    assert result[0].render_outcome is None
    assert result[0].clip_key is not None


@needs_ffmpeg
async def test_a_content_shaped_finding_triggers_one_reauthor_then_succeeds(tmp_path: Path) -> None:
    render = FakeRenderBackend(
        geometry_findings_sequence=[["[error] canvas_overflow: too much content"], []]
    )
    llm = FakeLLMProvider([a_payload_for(BlockType.TEXT_PANEL), no_annotations()])
    segment = an_authored_segment(0, BlockType.TEXT_PANEL, Tier.STATIC, duration_ms=DURATION_MS)
    context = _context(tmp_path, render=render, llm=llm)
    _write_narration(context.working_dir)

    result = await run_render_scene(segment, context)

    outcome = result[0].render_outcome
    assert outcome is not None
    assert outcome.attempts == 2
    assert outcome.reauthored is True
    assert outcome.fallback_used is False
    assert outcome.finding_codes == ["canvas_overflow"]
    assert result[0].clip_key is not None
    assert llm.responses == []  # both queued responses were consumed


@needs_ffmpeg
async def test_a_non_content_finding_skips_reauthor_and_falls_back(tmp_path: Path) -> None:
    # page_error is never content-retryable (rendering/geometry_findings.py) -- a bug in OUR
    # templates, not the LLM's content. The empty llm queue proves no re-author call was made:
    # FakeLLMProvider raises loudly if fill_block ever reached it.
    render = FakeRenderBackend(geometry_findings_sequence=[["[error] page_error: crash"], []])
    segment = an_authored_segment(0, BlockType.TEXT_PANEL, Tier.STATIC, duration_ms=DURATION_MS)
    context = _context(tmp_path, render=render, llm=FakeLLMProvider([]))
    _write_narration(context.working_dir)

    result = await run_render_scene(segment, context)

    outcome = result[0].render_outcome
    assert outcome is not None
    assert outcome.attempts == 2
    assert outcome.reauthored is False
    assert outcome.fallback_used is True
    assert outcome.finding_codes == ["page_error"]
    assert result[0].clip_key is not None


@needs_ffmpeg
async def test_a_reauthor_that_still_fails_falls_back_to_title_card(tmp_path: Path) -> None:
    render = FakeRenderBackend(
        geometry_findings_sequence=[
            ["[error] canvas_overflow: too much content"],
            ["[error] canvas_overflow: still too much"],
            [],
        ]
    )
    llm = FakeLLMProvider([a_payload_for(BlockType.TEXT_PANEL), no_annotations()])
    segment = an_authored_segment(0, BlockType.TEXT_PANEL, Tier.STATIC, duration_ms=DURATION_MS)
    context = _context(tmp_path, render=render, llm=llm)
    _write_narration(context.working_dir)

    result = await run_render_scene(segment, context)

    outcome = result[0].render_outcome
    assert outcome is not None
    assert outcome.attempts == 3
    assert outcome.reauthored is True
    assert outcome.fallback_used is True
    assert outcome.finding_codes == ["canvas_overflow", "canvas_overflow"]
    assert result[0].clip_key is not None


@needs_ffmpeg
async def test_the_fallback_title_card_downgrades_to_static_tier(tmp_path: Path) -> None:
    """T18I latency fix: a real render found one degraded ANIMATED-tier segment (three real
    attempts, all at Tier 2) cost more wall time alone than the other fourteen segments in the
    same job combined. The final fallback attempt gains nothing from full frame-by-frame
    animation -- a title card is Tier 0's own reference composition -- so it renders as
    Tier.STATIC regardless of the segment's originally assigned tier, while the two real
    attempts before it still render at the real tier, giving the actual content a genuine shot
    at full quality before giving up on it."""
    render = FakeRenderBackend(
        geometry_findings_sequence=[
            ["[error] canvas_overflow: too much content"],
            ["[error] canvas_overflow: still too much"],
            [],
        ]
    )
    llm = FakeLLMProvider([a_payload_for(BlockType.TEXT_PANEL), no_annotations()])
    segment = an_authored_segment(0, BlockType.TEXT_PANEL, Tier.ANIMATED, duration_ms=DURATION_MS)
    context = _context(tmp_path, render=render, llm=llm)
    _write_narration(context.working_dir)

    result = await run_render_scene(segment, context)

    assert result[0].render_outcome is not None
    assert result[0].render_outcome.fallback_used is True
    assert result[0].tier == Tier.STATIC
    assert result[0].clip_key is not None


@needs_ffmpeg
async def test_a_segment_already_rendered_is_skipped_not_re_rendered(tmp_path: Path) -> None:
    """T18I resume idempotency: a segment with clip_key set and its local clip still on disk (a
    checkpoint resume of an already-completed segment) must not re-render or re-mux."""
    render = FakeRenderBackend()
    segment = an_authored_segment(0, BlockType.TEXT_PANEL, Tier.STATIC, duration_ms=DURATION_MS)
    context = _context(tmp_path, render=render)
    clip = local_clip_path(context.working_dir, JOB_ID, 0)
    clip.parent.mkdir(parents=True, exist_ok=True)
    clip.write_bytes(b"already rendered")
    segment = segment.model_copy(update={"clip_key": "already/set"})

    result = await run_render_scene(segment, context)

    assert result[0].clip_key == "already/set"
    assert render.renders == []
    assert render.captures == []
    assert render.validate_geometry_calls == 0
