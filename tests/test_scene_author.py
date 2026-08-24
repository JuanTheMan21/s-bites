"""``core/graph/nodes/scene_author.py`` -- the scene-authoring call, and the guard that keeps it
downstream of measurement.

Two levels, deliberately. ``fill_slots`` is tested directly, because what it *sends* is the only
place "the skill pack demonstrably changes behaviour" can be observed against a fake that ignores
prompt content when answering. ``author_scene`` is tested through a one-node graph, because what it
adds on top is a state update and a refusal, both of which are about the node.
"""

from pathlib import Path

import pytest
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from core.graph import GraphContext, GraphState
from core.graph.nodes.scene_author import author_scene, fill_slots
from core.graph.retry_policy import build_transient_retry_policy
from core.graph.state import SegmentTask
from core.models import Segment, VideoJob, VisualIntent
from core.slot_schemas import slot_schema_for
from interfaces import SkillPack
from tests.fakes import (
    FakeLLMProvider,
    FakeRenderBackend,
    FakeSkillRegistry,
    FakeStorage,
    FakeTTSProvider,
)
from tests.segment_examples import a_segment
from tests.slot_examples import EXAMPLES

MEASURED_MS = 21_000


def a_skill_registry(
    *, scene_authoring: str = "SCENE AUTHORING PACK", house_style: str = "HOUSE STYLE PACK"
) -> FakeSkillRegistry:
    return FakeSkillRegistry(
        [
            SkillPack(name="scene-authoring", version="1.0", content=scene_authoring),
            SkillPack(name="house-style", version="1.0", content=house_style),
        ]
    )


def a_payload_for(intent: VisualIntent):
    """The believable payload ``tests/slot_examples.py`` already defines, as the schema instance
    a real ``LLMProvider`` would have returned."""
    return slot_schema_for(intent).model_validate(EXAMPLES[intent])


def a_context(skills: FakeSkillRegistry, llm: FakeLLMProvider, tmp_path: Path) -> GraphContext:
    return GraphContext(
        llm=llm,
        tts=FakeTTSProvider(),
        storage=FakeStorage(),
        skills=skills,
        render=FakeRenderBackend(),
        working_dir=tmp_path / "work",
        frame_budget=600,
        fps=24,
    )


def _fan_out(state: GraphState) -> list[Send]:
    return [
        Send("author_scene", SegmentTask(job_id=state["job"].job_id, segment=segment))
        for segment in state["segments"].values()
    ]


async def run_author_scene(segment: Segment, context: GraphContext) -> dict[int, Segment]:
    """One-node graph behind the same ``Send`` fan-out ``pipeline.py`` puts this node behind, and
    the same registration -- ``build_transient_retry_policy()``, never ``build_retry_policies()``,
    because ``fill_slots`` isolates its own ``StructuredOutputError`` retries per call (D73)."""
    builder = StateGraph(GraphState, context_schema=GraphContext)
    builder.add_node(
        "author_scene",
        author_scene,
        input_schema=SegmentTask,
        retry_policy=build_transient_retry_policy(),
    )
    builder.add_conditional_edges(START, _fan_out, ["author_scene"])
    builder.add_edge("author_scene", END)
    graph = builder.compile()

    job = VideoJob(job_id="job-1", topic="SQL injection")
    state = {"job": job, "segments": {segment.index: segment}}
    result = await graph.ainvoke(state, context=context)
    return result["segments"]


async def test_the_scene_authoring_and_house_style_packs_reach_the_call() -> None:
    skills = a_skill_registry(
        scene_authoring="DISTINCTIVE SCENE TEXT", house_style="DISTINCTIVE HOUSE STYLE"
    )
    llm = FakeLLMProvider([a_payload_for(VisualIntent.BULLET_LIST)])

    await fill_slots(
        llm, skills, a_segment(0, intent=VisualIntent.BULLET_LIST), duration_ms=MEASURED_MS
    )

    call = llm.calls[0]
    assert "DISTINCTIVE SCENE TEXT" in call.prompt
    assert call.system == "DISTINCTIVE HOUSE STYLE"


@pytest.mark.parametrize("intent", list(VisualIntent))
async def test_the_schema_asked_for_is_the_one_the_visual_intent_maps_to(
    intent: VisualIntent,
) -> None:
    """The whole indirection D2 rests on: the model is never asked for markup, it is asked for
    exactly the payload this intent's template consumes. Every intent, not a sample -- a mapping
    tested on one member is tested nowhere (D39)."""
    llm = FakeLLMProvider([a_payload_for(intent)])

    slots = await fill_slots(
        llm, a_skill_registry(), a_segment(0, intent=intent), duration_ms=MEASURED_MS
    )

    assert llm.calls[0].schema is slot_schema_for(intent)
    assert intent.value in llm.calls[0].prompt
    # And what comes back validates against that same schema -- the round trip through the
    # untyped dict Segment.slots stores it as (D29).
    assert slot_schema_for(intent).model_validate(slots)


async def test_the_measured_duration_reaches_the_prompt_in_seconds() -> None:
    """The pack's density rules are thresholds in seconds ("under 12 seconds", "12 to 30
    seconds"), so milliseconds in the prompt would be a unit the model has to convert itself."""
    llm = FakeLLMProvider([a_payload_for(VisualIntent.BULLET_LIST)])

    await fill_slots(
        llm, a_skill_registry(), a_segment(0, intent=VisualIntent.BULLET_LIST), duration_ms=21_000
    )

    assert "21.0 seconds" in llm.calls[0].prompt
    assert "21000" not in llm.calls[0].prompt


async def test_the_narration_the_scene_accompanies_reaches_the_prompt() -> None:
    """The pack's last section is entirely about not contradicting the narration and never
    inventing a number it does not supply -- which is unenforceable if the narration is not sent."""
    llm = FakeLLMProvider([a_payload_for(VisualIntent.BULLET_LIST)])
    segment = a_segment(0, intent=VisualIntent.BULLET_LIST).model_copy(
        update={"narration": "A parameterised query keeps the value a value."}
    )

    await fill_slots(llm, a_skill_registry(), segment, duration_ms=MEASURED_MS)

    assert "A parameterised query keeps the value a value." in llm.calls[0].prompt


async def test_the_node_returns_the_segment_with_its_slots_filled(tmp_path: Path) -> None:
    segment = a_segment(3, intent=VisualIntent.COMPARISON, duration_ms=MEASURED_MS)
    llm = FakeLLMProvider([a_payload_for(VisualIntent.COMPARISON)])

    authored = await run_author_scene(segment, a_context(a_skill_registry(), llm, tmp_path))

    assert set(authored) == {3}
    assert authored[3].slots == EXAMPLES[VisualIntent.COMPARISON]
    # Nothing measured or planned is disturbed -- this node adds slots and nothing else.
    assert authored[3].duration_ms == MEASURED_MS
    assert authored[3].title == segment.title


async def test_an_unmeasured_segment_raises_before_any_llm_call(tmp_path: Path) -> None:
    """Invariant 1's last line of defence. Unreachable while ``assign_tiers`` sits between this
    node and the TTS fan-out -- which is exactly why it is worth pinning: it is what makes
    reordering the graph fail loudly instead of authoring a scene against an invented duration."""
    segment = a_segment(0, intent=VisualIntent.BULLET_LIST, duration_ms=None)
    llm = FakeLLMProvider([a_payload_for(VisualIntent.BULLET_LIST)])

    with pytest.raises(ValueError, match="no measured duration_ms"):
        await run_author_scene(segment, a_context(a_skill_registry(), llm, tmp_path))

    assert llm.calls == []
