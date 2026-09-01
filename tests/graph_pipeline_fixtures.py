"""Shared setup for ``test_graph_pipeline.py`` and ``test_graph_resume.py``: a job, seeded fakes
for every interface, and the full sequence of LLM responses one run consumes.

Not a test module -- the same role ``tests/plan_segments_fixtures.py`` plays for ``plan_segments``.
Split out when the graph grew a second fan-out and the resume cases outgrew one file's 200 lines.

T18B: the LLM call sequence grew a step. ``plan_visuals`` (a new join, one call for the whole
video) now sits between narration and the ``author_scene`` fan-out, and each segment's fan-out
task makes one fill call *per planned block* rather than one call for the whole scene. Every
segment here is planned with exactly one TITLE block (segment 0's plan is ignored and forced
anyway; the rest are planned the same way here on purpose) so every fill call asks for the same
schema -- the fan-out's tasks reach the fake concurrently, in no guaranteed order, and
interchangeable payloads are what make that irrelevant rather than flaky (unchanged reasoning
from before T18B, just now applying to the fill step instead of the old single slot call).

T18E: ``author_scene`` now makes a SECOND, differently-shaped call per segment
(``SceneAnnotations``, after the fill call) -- and a real checkpointer (``AsyncSqliteSaver``,
which both graph-level test modules use) gives each segment's ``Send`` task a genuine suspension
point, so segments' fill/annotate calls interleave across each other in an order no fixed queue
position can predict (confirmed empirically, not assumed). ``FakeLLMProvider``'s own strict
positional FIFO is deliberately tested (``tests/test_fake_providers.py``) and stays as-is;
``PhaseQueueLLMProvider`` below is a local, narrower substitute for exactly this one scenario --
same isinstance-based type check, same "no response queued" failure, just matched by type
anywhere in the queue rather than strictly at position 0.
"""

import shutil
from pathlib import Path

import pytest

from core.annotation_plan_schema import SceneAnnotations
from core.block_schemas import TitleSlots
from core.block_types import BlockType, MotifName, SceneLayout
from core.graph import GraphContext
from core.models import Importance, VideoJob, VisualIntent
from core.outline_schema import Outline, SegmentPlan
from core.scene_plan_schema import PlannedBlock, SegmentScenePlan, VideoScenePlan
from core.scripting_schema import Narration
from interfaces import SkillPack
from interfaces.llm_provider import T
from tests.fakes import (
    FakeLLMProvider,
    FakeRenderBackend,
    FakeSkillRegistry,
    FakeStorage,
    FakeTTSProvider,
)
from tests.fakes.llm_provider import LLMCall


class PhaseQueueLLMProvider(FakeLLMProvider):
    """Like ``FakeLLMProvider``, but answers with the first queued response whose type matches
    the request, from anywhere in the queue -- not strictly the item at position 0. See this
    module's own docstring for why that is necessary here and nowhere else."""

    async def generate(self, prompt: str, schema: type[T], *, system: str | None = None) -> T:
        self._maybe_fail("generate")
        for i, response in enumerate(self.responses):
            if isinstance(response, schema):
                self.calls.append(LLMCall(prompt=prompt, schema=schema, system=system))
                return self.responses.pop(i)
        raise AssertionError(
            f"PhaseQueueLLMProvider has no response queued for a {schema.__name__} request. "
            "That is a test-authoring gap, not a backend failure -- queue one, or arm a "
            "real error with fail_next('generate', ...)."
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


def scene_plan(segment_count: int) -> VideoScenePlan:
    """The whole-video visual plan every run consumes -- one TITLE block per segment. Segment
    0's own entry is included for shape but ignored by ``plan_visuals`` (forced regardless)."""
    return VideoScenePlan(
        motif=MotifName.TERMINAL,
        segments=[
            SegmentScenePlan(
                segment_index=i,
                layout=SceneLayout.SINGLE,
                blocks=[PlannedBlock(block_type=BlockType.TITLE, role="Title", anchor_phrase=None)],
                continues_previous=False,
            )
            for i in range(segment_count)
        ],
    )


def slot_payloads(segment_count: int) -> list[TitleSlots]:
    """One fill-call payload per segment's one planned block -- interchangeable, since every
    segment plans exactly one TITLE block (see ``scene_plan``'s docstring for why that matters
    under concurrent fan-out)."""
    return [
        TitleSlots(headline=f"Headline {i}", subtitle=None, key_terms=[])
        for i in range(segment_count)
    ]


def _annotation_payloads(segment_count: int) -> list[SceneAnnotations]:
    """T18E: ``author_scene`` now makes one ``author_annotations`` call per segment too, after
    its block fill call(s) -- interchangeable with each other (empty is the common real answer,
    per the annotation-authoring pack's own "sparingly" guidance) for the same reason
    ``slot_payloads`` is."""
    return [SceneAnnotations(annotations=[]) for _ in range(segment_count)]


def author_scene_responses(segment_count: int) -> list[TitleSlots | SceneAnnotations]:
    """Every response one full pass through the ``author_scene`` fan-out consumes: one
    ``TitleSlots`` and one ``SceneAnnotations`` per segment. Order within this list no longer
    matters -- ``PhaseQueueLLMProvider`` matches by type, not position, which is what real
    interleaving across segments' ``Send`` tasks under a checkpointer needs."""
    return [*slot_payloads(segment_count), *_annotation_payloads(segment_count)]


def seeded_llm(segment_count: int) -> PhaseQueueLLMProvider:
    """The full call sequence a run makes: one Outline (plan_segments' outline call), one
    Narration per segment (its scripting calls), one VideoScenePlan (plan_visuals' single call),
    then ``author_scene_responses`` for the fan-out that follows."""
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
    return PhaseQueueLLMProvider(
        [outline, *narrations, scene_plan(segment_count), *author_scene_responses(segment_count)]
    )


def seeded_skills() -> FakeSkillRegistry:
    return FakeSkillRegistry(
        [
            SkillPack(name="outline", version="1.0", content="outline pack"),
            SkillPack(name="scripting", version="1.0", content="scripting pack"),
            SkillPack(name="visual-plan", version="1.0", content="visual plan pack"),
            SkillPack(name="scene-authoring", version="1.0", content="scene authoring pack"),
            SkillPack(name="house-style", version="1.0", content="house style pack"),
            SkillPack(
                name="annotation-authoring", version="1.0", content="annotation authoring pack"
            ),
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
