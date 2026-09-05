"""Wires the nodes into a graph: ``plan`` -> fan out one ``Send`` per segment -> ``synthesize`` ->
``assign_tiers`` -> ``plan_visuals`` -> fan out again -> ``author_scene`` -> ``collect_scenes`` ->
fan out a third time -> ``render_scene`` -> ``finalize``. The only file in the repo permitted to
build a ``StateGraph`` -- everything else under ``core/graph/`` supplies state, context, nodes, or
policy for this to assemble.

Each fan-out is separated from the next by a join, and the joins are what enforce Invariant 1's
ordering structurally: ``assign_tiers`` needs *every* segment's measured duration, so it cannot run
until the TTS fan-out converges; ``plan_visuals`` (T18B) needs every segment's narration and tier
to plan the whole video's visuals in one call, so it sits right after ``assign_tiers`` and before
the scene-authoring fan-out -- ``author_scene`` therefore cannot run until every segment has a
scene *plan*; ``collect_scenes`` (T18I: no longer empty -- see ``core/graph/nodes/
collect_scenes.py``) needs every segment's own authored annotations to enforce the whole-video
annotation budget; and ``render_scene`` (which composes and renders a segment's *authored* scene)
cannot run until that scene's blocks are filled either.
"""

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Send

from core.graph.context import GraphContext
from core.graph.node_timing import timed
from core.graph.nodes import (
    assign_tiers,
    author_scene,
    collect_scenes,
    finalize,
    plan_segments,
    plan_visuals,
    render_scene,
    synthesize_segment,
)
from core.graph.retry_policy import build_retry_policies, build_transient_retry_policy
from core.graph.state import GraphState, SegmentTask


def _fan_out_to_segments(state: GraphState) -> list[Send]:
    """One ``synthesize_segment`` task per segment ``plan_segments`` produced, run concurrently
    in the same superstep -- this is the fan-out, and it is what makes the resume test meaningful:
    a failure in one task must not cost the others their already-completed work."""
    return [
        Send("synthesize_segment", SegmentTask(job_id=state["job"].job_id, segment=segment))
        for segment in state["segments"].values()
    ]


def _fan_out_to_scene_authoring(state: GraphState) -> list[Send]:
    """The same shape again, after ``plan_visuals``: one ``author_scene`` task per segment, each
    carrying the measured, tiered, *and scene-planned* segment the join nodes just wrote back."""
    return [
        Send("author_scene", SegmentTask(job_id=state["job"].job_id, segment=segment))
        for segment in state["segments"].values()
    ]


def _fan_out_to_rendering(state: GraphState) -> list[Send]:
    """The same shape a third time, after ``collect_scenes``: one ``render_scene`` task per
    segment, each carrying the measured, tiered, *and* authored segment."""
    return [
        Send("render_scene", SegmentTask(job_id=state["job"].job_id, segment=segment))
        for segment in state["segments"].values()
    ]


def build_graph(checkpointer: BaseCheckpointSaver | None = None) -> CompiledStateGraph:
    """Compile the skeleton graph. ``checkpointer`` is required for resume to mean anything --
    without one, LangGraph keeps no state between ``ainvoke`` calls at all."""
    builder = StateGraph(GraphState, context_schema=GraphContext)

    # Every node callable is wrapped with timed(...) (T18E, D121/D122) -- a plain start/elapsed
    # log line, no new GraphState field. functools.wraps keeps LangGraph's own Runtime-injection
    # signature inspection working through the wrapper (core/graph/node_timing.py's docstring).

    # Not build_retry_policies(): plan_segments isolates its own StructuredOutputError retries
    # internally (core/graph/nodes/structured_retry.py) -- attaching the bounded policy here too
    # would let an exhausted local retry re-trigger a whole-node retry for the same error.
    builder.add_node(
        "plan_segments",
        timed("plan_segments", plan_segments),
        retry_policy=build_transient_retry_policy(),
    )
    builder.add_node(
        "synthesize_segment",
        timed("synthesize_segment", synthesize_segment),
        input_schema=SegmentTask,
        retry_policy=build_retry_policies(),
    )
    # No retry policy: assign_tiers reaches nothing outside the process, so there is no transient
    # failure for one to absorb. Its only error is an unmeasured segment, which a retry cannot fix.
    builder.add_node("assign_tiers", timed("assign_tiers", assign_tiers))
    # Transient-only, for the same reason plan_segments is -- plan_visuals's one LLM call carries
    # its own StructuredOutputError budget (D73), via generate_with_bounded_retries.
    builder.add_node(
        "plan_visuals",
        timed("plan_visuals", plan_visuals),
        retry_policy=build_transient_retry_policy(),
    )
    # Transient-only, for the same reason plan_segments is -- author_scene's LLM calls each carry
    # their own StructuredOutputError budget (D73).
    builder.add_node(
        "author_scene",
        timed("author_scene", author_scene),
        input_schema=SegmentTask,
        retry_policy=build_transient_retry_policy(),
    )
    # No policy: pure, in-process bookkeeping over already-authored content -- no LLMProvider
    # call, no I/O, nothing here can raise the way an adapter call could.
    builder.add_node("collect_scenes", timed("collect_scenes", collect_scenes))
    # Transient-only: render_scene makes no LLMProvider call, so there is no StructuredOutputError
    # to isolate -- only RenderFailed (retryable) and CompositionInvalid (our own gate, matches
    # neither policy, propagates immediately).
    builder.add_node(
        "render_scene",
        timed("render_scene", render_scene),
        input_schema=SegmentTask,
        retry_policy=build_transient_retry_policy(),
    )
    # finalize now does real I/O (concat + Storage.put_file) that can raise RenderFailed, where it
    # previously did none -- transient-only, same reasoning as render_scene.
    builder.add_node(
        "finalize", timed("finalize", finalize), retry_policy=build_transient_retry_policy()
    )

    builder.add_edge(START, "plan_segments")
    builder.add_conditional_edges("plan_segments", _fan_out_to_segments, ["synthesize_segment"])
    builder.add_edge("synthesize_segment", "assign_tiers")
    builder.add_edge("assign_tiers", "plan_visuals")
    builder.add_conditional_edges("plan_visuals", _fan_out_to_scene_authoring, ["author_scene"])
    builder.add_edge("author_scene", "collect_scenes")
    builder.add_conditional_edges("collect_scenes", _fan_out_to_rendering, ["render_scene"])
    builder.add_edge("render_scene", "finalize")
    builder.add_edge("finalize", END)

    return builder.compile(checkpointer=checkpointer)
