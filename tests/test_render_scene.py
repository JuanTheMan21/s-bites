"""``core/graph/nodes/render_scene.py`` -- render, mux, and persist one segment's clip.

Same split ``tests/test_render_segment.py`` already makes: Tier 0/1 run through
``FakeRenderBackend`` + real ffmpeg and prove this node's own new code (the mux + the
``Storage.put_file`` + ``clip_key``). Tier 2 *dispatch* is already covered offline by
``test_render_segment.py`` -- duplicating it here would mean running real ffmpeg over
``FakeRenderBackend.render``'s placeholder bytes, which its own docstring already says is not a
real MP4 ("T18's mux work must run against the real local adapter, not this").
"""

import shutil
import wave
from pathlib import Path

import pytest
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from core.block_types import BlockType
from core.graph import GraphContext, GraphState
from core.graph.nodes.render_scene import SEGMENT_CLIP_KEY, local_clip_path, render_scene
from core.graph.nodes.synthesize import local_narration_path
from core.graph.retry_policy import build_transient_retry_policy
from core.graph.state import SegmentTask
from core.models import Segment, Tier, VideoJob
from interfaces import CompositionInvalid
from tests.fakes import FakeLLMProvider, FakeRenderBackend, FakeSkillRegistry, FakeStorage
from tests.fakes.tts_provider import FakeTTSProvider
from tests.segment_examples import an_authored_segment

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is not on PATH")

JOB_ID = "job-1"
DURATION_MS = 4_000
SAMPLE_RATE_HZ = 8_000


def _write_narration(working_dir: Path) -> None:
    """Stand in for ``synthesize_segment`` having already run -- render_scene reads this file
    directly off disk rather than calling TTSProvider itself."""
    path = local_narration_path(working_dir, JOB_ID, 0)
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = round(DURATION_MS / 1000 * SAMPLE_RATE_HZ)
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(1)
        audio.setframerate(SAMPLE_RATE_HZ)
        audio.writeframes(b"\x80" * frames)


def a_context(tmp_path: Path, *, storage: FakeStorage, render: FakeRenderBackend) -> GraphContext:
    return GraphContext(
        llm=FakeLLMProvider([]),
        tts=FakeTTSProvider(),
        storage=storage,
        skills=FakeSkillRegistry([]),
        render=render,
        working_dir=tmp_path / "work",
        frame_budget=1400,
        fps=24,
    )


def _fan_out(state: GraphState) -> list[Send]:
    return [
        Send("render_scene", SegmentTask(job_id=state["job"].job_id, segment=segment))
        for segment in state["segments"].values()
    ]


async def run_render_scene(segment: Segment, context: GraphContext) -> dict[int, Segment]:
    """One-node graph behind the same ``Send`` fan-out and registration ``pipeline.py`` uses."""
    builder = StateGraph(GraphState, context_schema=GraphContext)
    builder.add_node(
        "render_scene",
        render_scene,
        input_schema=SegmentTask,
        retry_policy=build_transient_retry_policy(),
    )
    builder.add_conditional_edges(START, _fan_out, ["render_scene"])
    builder.add_edge("render_scene", END)
    graph = builder.compile()

    job = VideoJob(job_id=JOB_ID, topic="a nice topic")
    state = {"job": job, "segments": {segment.index: segment}}
    result = await graph.ainvoke(state, context=context)
    return result["segments"]


@needs_ffmpeg
async def test_tier_static_renders_muxes_and_persists_a_playable_clip(tmp_path: Path) -> None:
    segment = an_authored_segment(0, BlockType.TITLE, Tier.STATIC, duration_ms=DURATION_MS)
    storage = FakeStorage()
    context = a_context(tmp_path, storage=storage, render=FakeRenderBackend())
    _write_narration(context.working_dir)

    result = await run_render_scene(segment, context)

    updated = result[0]
    expected_key = SEGMENT_CLIP_KEY.format(job_id=JOB_ID, index=0)
    assert updated.clip_key == expected_key
    assert expected_key in storage.objects
    assert storage.content_types[expected_key] == "video/mp4"

    local_clip = local_clip_path(context.working_dir, JOB_ID, 0)
    assert local_clip.exists() and local_clip.stat().st_size > 0


@needs_ffmpeg
async def test_tier_reveal_renders_muxes_and_persists_a_playable_clip(tmp_path: Path) -> None:
    segment = an_authored_segment(0, BlockType.DIAGRAM_CHAIN, Tier.REVEAL, duration_ms=DURATION_MS)
    storage = FakeStorage()
    context = a_context(tmp_path, storage=storage, render=FakeRenderBackend())
    _write_narration(context.working_dir)

    result = await run_render_scene(segment, context)

    assert result[0].clip_key == SEGMENT_CLIP_KEY.format(job_id=JOB_ID, index=0)


async def test_a_lint_finding_raises_before_any_mux_or_storage_write(tmp_path: Path) -> None:
    segment = an_authored_segment(0, BlockType.TEXT_PANEL, Tier.STATIC, duration_ms=DURATION_MS)
    storage = FakeStorage()
    render = FakeRenderBackend(findings=["[error] fake_finding: something is wrong"])
    context = a_context(tmp_path, storage=storage, render=render)
    _write_narration(context.working_dir)

    with pytest.raises(CompositionInvalid, match="fake_finding"):
        await run_render_scene(segment, context)

    assert storage.objects == {}
