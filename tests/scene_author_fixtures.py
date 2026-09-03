"""Shared setup for ``test_scene_author.py`` (``fill_block``) and ``test_author_scene_node.py``
(``author_scene``) -- split out when the combined file crossed the 200-line ceiling.

Not a test module -- the same role ``tests/graph_pipeline_fixtures.py`` plays for the full graph.
"""

from pathlib import Path

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from core.annotation_plan_schema import SceneAnnotations
from core.block_schemas import block_schema_for
from core.block_types import BlockType
from core.graph import GraphContext, GraphState
from core.graph.nodes.scene_author import author_scene
from core.graph.retry_policy import build_transient_retry_policy
from core.graph.state import SegmentTask
from core.models import Segment
from core.scene_schemas import ComposedBlock, ComposedScene
from core.video_job import VideoJob
from interfaces import SkillPack
from tests.block_examples import EXAMPLES
from tests.fakes import (
    FakeLLMProvider,
    FakeRenderBackend,
    FakeSkillRegistry,
    FakeStorage,
    FakeTTSProvider,
)
from tests.segment_examples import a_segment

MEASURED_MS = 21_000


def a_skill_registry(
    *,
    scene_authoring: str = "SCENE AUTHORING PACK",
    house_style: str = "HOUSE STYLE PACK",
    annotation_authoring: str = "ANNOTATION AUTHORING PACK",
) -> FakeSkillRegistry:
    return FakeSkillRegistry(
        [
            SkillPack(name="scene-authoring", version="1.0", content=scene_authoring),
            SkillPack(name="house-style", version="1.0", content=house_style),
            SkillPack(name="annotation-authoring", version="1.0", content=annotation_authoring),
        ]
    )


def no_annotations() -> SceneAnnotations:
    """``author_scene`` always calls ``author_annotations`` once every block is filled -- queue
    this after a test's block payloads to answer with none, the common case."""
    return SceneAnnotations(annotations=[])


def a_payload_for(block_type: BlockType):
    """The believable payload ``tests/block_examples.py`` already defines, as the schema instance
    a real ``LLMProvider`` would have returned."""
    return block_schema_for(block_type).model_validate(EXAMPLES[block_type])


def a_planned_block(block_type: BlockType, *, role: str = "role") -> ComposedBlock:
    """One block, planned but not yet filled -- exactly what ``plan_visuals`` hands off."""
    return ComposedBlock(block_type=block_type, role=role, anchor_phrase=None)


def a_planned_segment(index: int, *blocks: ComposedBlock, layout: str = "single") -> Segment:
    """A segment carrying a scene plan with unfilled blocks -- the state ``author_scene`` expects
    to receive, one step downstream of ``plan_visuals``."""
    scene = ComposedScene(
        motif="terminal", layout=layout, blocks=list(blocks), continues_previous=False
    )
    return a_segment(index, duration_ms=MEASURED_MS).model_copy(
        update={"scene": scene.model_dump()}
    )


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
    because ``fill_block`` isolates its own ``StructuredOutputError`` retries per call (D73)."""
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
