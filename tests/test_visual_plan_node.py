"""``core/graph/nodes/visual_plan.py::plan_visuals`` -- the whole-video visual plan call, and
(T18E) its one bounded re-ask when the first plan leaves a segment's narration clearly calling
for a block type used nowhere in the video (``core/block_triggers.py``, D121/D122).
"""

from pathlib import Path

from langgraph.graph import END, START, StateGraph

from core.block_types import BlockType, MotifName, SceneLayout
from core.graph import GraphContext, GraphState
from core.graph.nodes.visual_plan import plan_visuals
from core.scene_plan_schema import PlannedBlock, SegmentScenePlan, VideoScenePlan
from core.scene_schemas import ComposedScene
from interfaces import SkillPack
from tests.fakes import (
    FakeLLMProvider,
    FakeRenderBackend,
    FakeSkillRegistry,
    FakeStorage,
    FakeTTSProvider,
)
from tests.segment_examples import a_segment
from tests.test_block_triggers import TIMELINE_NARRATION


def _skills() -> FakeSkillRegistry:
    return FakeSkillRegistry(
        [
            SkillPack(name="visual-plan", version="1.0", content="VISUAL PLAN PACK"),
            SkillPack(name="house-style", version="1.0", content="HOUSE STYLE PACK"),
        ]
    )


def _context(llm: FakeLLMProvider, tmp_path: Path) -> GraphContext:
    return GraphContext(
        llm=llm,
        tts=FakeTTSProvider(),
        storage=FakeStorage(),
        skills=_skills(),
        render=FakeRenderBackend(),
        working_dir=tmp_path / "work",
        frame_budget=600,
        fps=24,
    )


def _plan(motif: str, *, blocks: dict[int, BlockType]) -> VideoScenePlan:
    return VideoScenePlan(
        motif=motif,
        segments=[
            SegmentScenePlan(
                segment_index=index,
                layout=SceneLayout.SINGLE,
                blocks=[PlannedBlock(block_type=block_type, role="role", anchor_phrase=None)],
                continues_previous=False,
            )
            for index, block_type in blocks.items()
        ],
    )


async def _run_plan_visuals(segments: dict, context: GraphContext) -> dict:
    builder = StateGraph(GraphState, context_schema=GraphContext)
    builder.add_node("plan_visuals", plan_visuals)
    builder.add_edge(START, "plan_visuals")
    builder.add_edge("plan_visuals", END)
    graph = builder.compile()

    from core.models import VideoJob

    job = VideoJob(job_id="job-1", topic="a topic")
    result = await graph.ainvoke({"job": job, "segments": segments}, context=context)
    return result["segments"]


async def test_no_missed_opportunity_makes_exactly_one_call(tmp_path: Path) -> None:
    segments = {
        0: a_segment(0).model_copy(update={"narration": "Title."}),
        1: a_segment(1).model_copy(update={"narration": "Ordinary narration."}),
    }
    plan = _plan(MotifName.TERMINAL, blocks={0: BlockType.TITLE, 1: BlockType.TEXT_PANEL})
    llm = FakeLLMProvider([plan])

    await _run_plan_visuals(segments, _context(llm, tmp_path))

    assert len(llm.calls) == 1


async def test_a_missed_opportunity_triggers_exactly_one_bounded_reask(tmp_path: Path) -> None:
    """T18E, D121/D122: the first plan never used TIMELINE despite segment 1's narration clearly
    calling for it -- the second (and final) plan is taken even though the test's own second
    response still doesn't fix it, proving there is no third call."""
    segments = {
        0: a_segment(0).model_copy(update={"narration": "Title."}),
        1: a_segment(1).model_copy(update={"narration": TIMELINE_NARRATION}),
    }
    first_plan = _plan(MotifName.TERMINAL, blocks={0: BlockType.TITLE, 1: BlockType.TEXT_PANEL})
    second_plan = _plan(MotifName.BLUEPRINT, blocks={0: BlockType.TITLE, 1: BlockType.STAT_CALLOUT})
    llm = FakeLLMProvider([first_plan, second_plan])

    updated = await _run_plan_visuals(segments, _context(llm, tmp_path))

    assert len(llm.calls) == 2
    # The second plan is final, even though it still doesn't use TIMELINE -- no third call.
    scene = ComposedScene.model_validate(updated[1].scene)
    assert scene.blocks[0].block_type == BlockType.STAT_CALLOUT
    assert scene.motif == MotifName.BLUEPRINT
