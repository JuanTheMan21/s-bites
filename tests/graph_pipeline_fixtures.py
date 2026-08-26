"""Shared setup for ``test_graph_pipeline.py`` and ``test_graph_resume.py``: a job, seeded fakes
for every interface, and the full sequence of LLM responses one run consumes.

Not a test module -- the same role ``tests/plan_segments_fixtures.py`` plays for ``plan_segments``.
Split out when the graph grew a second fan-out and the resume cases outgrew one file's 200 lines.
"""

import shutil
from pathlib import Path

import pytest

from core.graph import GraphContext
from core.models import Importance, VideoJob, VisualIntent
from core.outline_schema import Outline, SegmentPlan
from core.scripting_schema import Narration
from core.slot_schemas import TitleCardSlots
from interfaces import SkillPack
from tests.fakes import (
    FakeLLMProvider,
    FakeRenderBackend,
    FakeSkillRegistry,
    FakeStorage,
    FakeTTSProvider,
)

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is not on PATH")

# 100s targets 4 segments (round(100_000 / 1000 / 28) == 4) -- enough to make fan-out and a
# single failure among several concurrent tasks meaningful, small enough to stay fast.
TARGET_DURATION_MS = 100_000

# Zero, not the .env default -- T18's render_scene fan-out now sits downstream of tiering, and
# core/tier_resolver.py starts every segment on Tier.STATIC unconditionally, only promoting a
# segment if doing so fits the budget. A budget of 0 therefore keeps every segment on Tier 0
# deterministically, regardless of FakeTTSProvider's (tiny) synthesized durations -- which matters
# here specifically because Tier 0/1 render through real ffmpeg (mux/frames_to_clip.py) and
# produce a real MP4, where Tier 2 would dispatch to FakeRenderBackend.render's placeholder bytes
# (its own docstring: "T18's mux work must run against the real local adapter, not this"). What
# varies *with* the budget is tested in test_tiering_node.py, which builds its own context.
FRAME_BUDGET = 0
FPS = 24


def a_job() -> VideoJob:
    return VideoJob(job_id="job-1", topic="SQL injection", target_duration_ms=TARGET_DURATION_MS)


def slot_payloads(segment_count: int) -> list[TitleCardSlots]:
    """One payload per segment for the ``author_scene`` fan-out.

    Every segment in these tests is a title card, so the payloads are interchangeable -- which
    matters, because this is the first place responses are popped off the queue *concurrently*.
    The order the fan-out's tasks reach the fake is not deterministic; identical payloads make
    that irrelevant rather than flaky.
    """
    return [TitleCardSlots(headline=f"Headline {i}", subtitle=None) for i in range(segment_count)]


def seeded_llm(segment_count: int) -> FakeLLMProvider:
    """The full call sequence a run makes: one Outline (plan_segments' outline call), one
    Narration per segment (its scripting calls, in index order), then one slot payload per
    segment (the author_scene fan-out)."""
    outline = Outline(
        segments=[
            SegmentPlan(
                title=f"Title {i}",
                summary=f"Summary {i}",
                visual_intent=VisualIntent.TITLE_CARD,
                importance=Importance.NORMAL,
            )
            for i in range(segment_count)
        ]
    )
    narrations = [Narration(text=f"Narration {i}.") for i in range(segment_count)]
    return FakeLLMProvider([outline, *narrations, *slot_payloads(segment_count)])


def seeded_skills() -> FakeSkillRegistry:
    return FakeSkillRegistry(
        [
            SkillPack(name="outline", version="1.0", content="outline pack"),
            SkillPack(name="scripting", version="1.0", content="scripting pack"),
            SkillPack(name="scene-authoring", version="1.0", content="scene authoring pack"),
            SkillPack(name="house-style", version="1.0", content="house style pack"),
        ]
    )


def a_context(
    tmp_path: Path, *, tts: FakeTTSProvider, storage: FakeStorage, llm: FakeLLMProvider
) -> GraphContext:
    return GraphContext(
        llm=llm,
        tts=tts,
        storage=storage,
        skills=seeded_skills(),
        render=FakeRenderBackend(),
        working_dir=tmp_path / "work",
        frame_budget=FRAME_BUDGET,
        fps=FPS,
    )
