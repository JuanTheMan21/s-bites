"""Wires the nodes into a graph: ``plan`` -> fan out one ``Send`` per segment -> ``synthesize`` ->
``finalize``. The only file in the repo permitted to build a ``StateGraph`` -- everything else
under ``core/graph/`` supplies state, context, nodes, or policy for this to assemble.
"""

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Send

from core.graph.context import GraphContext
from core.graph.nodes import finalize, plan_segments, synthesize_segment
from core.graph.retry_policy import build_retry_policies
from core.graph.state import GraphState, SegmentTask


def _fan_out_to_segments(state: GraphState) -> list[Send]:
    """One ``synthesize_segment`` task per segment ``plan_segments`` produced, run concurrently
    in the same superstep -- this is the fan-out, and it is what makes the resume test meaningful:
    a failure in one task must not cost the others their already-completed work."""
    return [
        Send("synthesize_segment", SegmentTask(job_id=state["job"].job_id, segment=segment))
        for segment in state["segments"].values()
    ]


def build_graph(checkpointer: BaseCheckpointSaver | None = None) -> CompiledStateGraph:
    """Compile the skeleton graph. ``checkpointer`` is required for resume to mean anything --
    without one, LangGraph keeps no state between ``ainvoke`` calls at all."""
    builder = StateGraph(GraphState, context_schema=GraphContext)

    builder.add_node("plan_segments", plan_segments)
    builder.add_node(
        "synthesize_segment",
        synthesize_segment,
        input_schema=SegmentTask,
        retry_policy=build_retry_policies(),
    )
    builder.add_node("finalize", finalize)

    builder.add_edge(START, "plan_segments")
    builder.add_conditional_edges("plan_segments", _fan_out_to_segments, ["synthesize_segment"])
    builder.add_edge("synthesize_segment", "finalize")
    builder.add_edge("finalize", END)

    return builder.compile(checkpointer=checkpointer)
