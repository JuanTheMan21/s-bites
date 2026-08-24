"""The scene-authoring call: one ``LLMProvider.generate`` per segment producing the slot payload
for that segment's visual intent, from the ``scene-authoring`` pack and the ``house-style`` pack it
is always interpolated alongside.

Per D2 the LLM never writes HTML -- it fills a small structured payload and a hand-authored Jinja
template (T17) turns that into markup. ``core.slot_schemas.slot_schema_for`` is the whole
indirection: it turns "this segment wants a comparison" into the class handed to ``generate``.
"""

from typing import Any

from langgraph.runtime import Runtime

from core.graph.context import GraphContext
from core.graph.nodes.skill_prompt import load_step_prompt
from core.graph.nodes.structured_retry import generate_with_bounded_retries
from core.graph.state import SegmentTask
from core.models import Segment
from core.slot_schemas import slot_schema_for
from interfaces import LLMProvider, SkillRegistry

SCENE_AUTHORING_PACK = "scene-authoring"


async def fill_slots(
    llm: LLMProvider, skills: SkillRegistry, segment: Segment, *, duration_ms: int
) -> dict[str, Any]:
    """Fill ``segment``'s slot payload, given how long the scene is actually on screen.

    ``duration_ms`` is a required parameter rather than read off ``segment.duration_ms`` inside
    this function, and that is Invariant 1's structural enforcement, not a redundancy:
    ``Segment.duration_ms`` is nullable because it is empty until the TTS adapter measures the
    audio it wrote, so a caller who has not measured yet cannot satisfy this signature without
    inventing a number in plain sight. Calling this early is a type error.

    The returned dict is ``slot_schema_for(segment.visual_intent)``'s own ``model_dump()`` -- it
    is stored on ``Segment.slots``, which is untyped (D29), so validate it back through
    ``slot_schema_for`` at the point of use rather than trusting the dict's shape.
    """
    step_prompt = await load_step_prompt(skills, SCENE_AUTHORING_PACK)
    # Seconds, not milliseconds: the pack's density rules are written as thresholds in seconds
    # ("under 12 seconds", "12 to 30 seconds", "over 30 seconds"), so this is the unit it reasons in.
    prompt = (
        f"{step_prompt.step}\n\n"
        f"Visual intent: {segment.visual_intent.value}\n"
        f"Measured narration duration: {duration_ms / 1000:.1f} seconds\n"
        f"Segment title: {segment.title}\n"
        f"Narration this scene accompanies:\n{segment.narration}"
    )
    payload = await generate_with_bounded_retries(
        llm,
        prompt,
        slot_schema_for(segment.visual_intent),
        system=step_prompt.house_style,
    )
    return payload.model_dump()


async def author_scene(state: SegmentTask, runtime: Runtime[GraphContext]) -> dict:
    """Author one segment's scene and return it with ``slots`` filled in.

    One task per segment in the fan-out that follows ``assign_tiers``. Registered with
    ``build_transient_retry_policy()``, never ``build_retry_policies()`` -- ``fill_slots`` isolates
    its own ``StructuredOutputError`` retries per call, and a node-level policy that also matched
    that error would let an exhausted local retry re-trigger a whole-node redo (D73).

    Raises:
        ValueError: the segment has no measured duration. Unreachable while ``assign_tiers`` sits
            between this node and the TTS fan-out -- it exists so that reordering the graph fails
            loudly here instead of quietly authoring a scene against an invented duration.
    """
    segment = state["segment"]
    if segment.duration_ms is None:
        raise ValueError(
            f"segment {segment.index} has no measured duration_ms, so its scene cannot be "
            "authored. Scene authoring runs *after* narration is synthesised and measured "
            "(Invariant 1) -- how much text fits on screen is a function of how long it is up."
        )

    slots = await fill_slots(
        runtime.context.llm, runtime.context.skills, segment, duration_ms=segment.duration_ms
    )
    return {"segments": {segment.index: segment.model_copy(update={"slots": slots})}}
