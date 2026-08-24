"""The join node: every segment's tier, decided once every segment has been measured.

The first caller of ``core/tier_resolver.py`` and of ``core/frame_budget.py`` -- both were built
whole and tested exhaustively at T5/T6 and have had no caller until now. Nothing here re-implements
either; this node's whole job is to sit at the one point in the graph where the inputs they need
exist.

That point is not negotiable. ``resolve_tiers`` needs *every* segment's measured ``duration_ms``,
which only exists once the ``synthesize_segment`` fan-out has converged -- so this is a join node
after that fan-out, never a per-segment task inside it. Invariant 1 in the shape of the graph
rather than in a comment.
"""

from langgraph.runtime import Runtime

from core.frame_budget import scale_frame_budget
from core.graph.context import GraphContext
from core.graph.state import GraphState
from core.tier_resolver import resolve_tiers


async def assign_tiers(state: GraphState, runtime: Runtime[GraphContext]) -> dict:
    """Assign every segment a render tier and return them with ``tier`` filled in.

    ``context.frame_budget`` is the base budget for a default-length video; the budget actually
    spent is that scaled to this job's requested length, so a ten-minute video is not squeezed
    into a seven-minute video's render time (and a two-minute one does not get all of it).

    Raises:
        ValueError: any segment is unmeasured -- raised by ``resolve_tiers`` itself, whose message
            already explains why tier assignment cannot precede narration. Unreachable given the
            graph's shape, which is the point of letting it propagate rather than pre-checking.
    """
    context = runtime.context
    segments = state["segments"]
    budget = scale_frame_budget(context.frame_budget, state["job"].target_duration_ms)
    plan = resolve_tiers(list(segments.values()), frame_budget=budget, fps=context.fps)
    return {
        "segments": {
            index: segment.model_copy(update={"tier": plan.tier_for(index)})
            for index, segment in segments.items()
        }
    }
