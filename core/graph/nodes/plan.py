"""The graph node that turns a ``VideoJob`` into narrated segments.

Still one node, at the same position T14 left it (D70): ``plan_segments`` still runs once,
before the ``Send`` fan-out, with the same return shape (``{"segments": {index: Segment}}``).
What changed is its body -- it now runs one real ``LLMProvider`` call for the outline plus one
more per segment for its narration, instead of building a deterministic placeholder.
``core/graph/nodes/outline.py`` and ``.../scripting.py`` hold each call's own prompt-building and
schema; this module just sequences them.
"""

from langgraph.runtime import Runtime

from core.graph.context import GraphContext
from core.graph.nodes.outline import generate_outline
from core.graph.nodes.scripting import write_narration
from core.graph.state import GraphState


async def plan_segments(state: GraphState, runtime: Runtime[GraphContext]) -> dict:
    """Outline the job, then narrate every segment the outline produced.

    Both calls happen inside this one node invocation rather than as separate graph nodes, so a
    transient failure anywhere in it retries the whole thing under the node-level ``RetryPolicy``
    already attached in ``pipeline.py`` -- redoing an outline call on retry is wasted tokens, not
    a correctness risk, unlike redoing TTS.
    """
    context = runtime.context
    job = state["job"]

    segments = await generate_outline(context.llm, context.skills, job)
    segments = await write_narration(context.llm, context.skills, segments)
    return {"segments": segments}
