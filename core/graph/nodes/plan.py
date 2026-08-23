"""Stands in for T15's real outline+script node. Pure -- no interface call -- because narration
worth calling an ``LLMProvider`` for doesn't exist until T15 writes it. What this node fixes is
the graph *shape*: something before the fan-out has to turn a ``VideoJob`` into a list of
segments. T15 replaces this function's body; the node it plugs into and the fan-out reading its
output don't change.
"""

from core.graph.state import GraphState
from core.models import Importance, Segment, VisualIntent


async def plan_segments(state: GraphState) -> dict:
    """Deterministic placeholder segments, one per ``VideoJob.segment_count``.

    Narration is a fixed placeholder sentence rather than anything derived from the topic --
    there is no scripting node yet to derive it from, and inventing prose here would only have
    to be thrown away at T15.
    """
    job = state["job"]
    segments = {
        index: Segment(
            index=index,
            title=f"Segment {index}",
            summary=f"Placeholder segment {index} of {job.topic!r}.",
            visual_intent=VisualIntent.TITLE_CARD,
            importance=Importance.NORMAL,
            narration=f"This is placeholder narration for segment {index}.",
        )
        for index in range(job.segment_count)
    }
    return {"segments": segments}
