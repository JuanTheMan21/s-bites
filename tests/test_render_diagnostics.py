"""T18M: ``core/graph/nodes/render_diagnostics.py`` and ``render_scene.py``'s use of it -- the
whole reason segments 4/12 of job ``eaebea14d7484ef19a82fcd7881f94d3`` couldn't be diagnosed was
that the failing scene and findings were thrown away on every attempt. Both a failed attempt's
scene and its raw findings must now be persisted, one diagnostic per attempt."""

import json
from pathlib import Path

from core.block_types import BlockType
from core.graph import GraphContext
from core.models import Tier
from tests.fakes import FakeLLMProvider, FakeRenderBackend, FakeStorage
from tests.fakes.tts_provider import FakeTTSProvider
from tests.scene_author_fixtures import a_payload_for, a_skill_registry, no_annotations
from tests.segment_examples import an_authored_segment
from tests.test_render_scene import DURATION_MS, JOB_ID, _write_narration, needs_ffmpeg
from tests.test_render_scene import run_render_scene as _run


def _context(tmp_path: Path, *, render: FakeRenderBackend, llm: FakeLLMProvider) -> GraphContext:
    return GraphContext(
        llm=llm,
        tts=FakeTTSProvider(),
        storage=FakeStorage(),
        skills=a_skill_registry(),
        render=render,
        working_dir=tmp_path / "work",
        frame_budget=600,
        fps=24,
    )


@needs_ffmpeg
async def test_every_failed_attempt_persists_its_own_diagnostic(tmp_path: Path) -> None:
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

    await _run(segment, context)

    diagnostic_keys = sorted(k for k in context.storage.objects if "failed_scene_attempt" in k)
    assert diagnostic_keys == [
        f"{JOB_ID}/segments/0/failed_scene_attempt1.json",
        f"{JOB_ID}/segments/0/failed_scene_attempt2.json",
    ]
    first = json.loads(context.storage.objects[diagnostic_keys[0]])
    assert first["findings"] == ["[error] canvas_overflow: too much content"]
    assert first["scene"]["blocks"]
