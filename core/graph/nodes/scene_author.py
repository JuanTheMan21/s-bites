"""The scene-authoring call: ``plan_visuals`` (the join node before this fan-out) has already
decided every segment's layout and which blocks make it up, each with ``payload=None``. This
node fills each block's content with its own ``LLMProvider.generate`` call -- one call per
block, never one call for the whole scene, which is the whole answer to D29 (Azure strict
structured output cannot express a discriminated union): every call is constrained to one
block's own concrete schema, never a union of possible shapes.

Per D2 the LLM never writes HTML -- it fills a small structured payload and a hand-authored
Jinja block partial (``rendering/templates/_block_*.html``) turns that into markup.
``core.block_schemas.block_schema_for`` is the whole indirection: it turns "this block is a
code_panel" into the class handed to ``generate``.

T18E: once every block is filled, this node also authors the scene's annotations (``core/graph/
nodes/annotation_author.py``) -- moved here from ``plan_visuals``, which had to ask for a real
``target_item_index`` before any block had content to index into, and could only ever get ``null``
back (D121/D122). The per-block ``fill_block`` calls run concurrently (``asyncio.gather``), not
one at a time -- they are fully independent, and the Azure adapter's own semaphore already bounds
real concurrency regardless of caller pattern (D121 reopens the prior sequential-comprehension
choice).
"""

import asyncio
from typing import Any

from langgraph.runtime import Runtime

from core.block_schemas import block_schema_for
from core.graph.context import GraphContext
from core.graph.nodes.annotation_author import author_annotations
from core.graph.nodes.skill_prompt import load_step_prompt
from core.graph.nodes.structured_retry import generate_with_bounded_retries
from core.graph.state import SegmentTask
from core.models import Segment
from core.scene_content_normalize import normalize_block_payload
from core.scene_schemas import ComposedBlock, ComposedScene
from interfaces import LLMProvider, SkillRegistry

SCENE_AUTHORING_PACK = "scene-authoring"


async def fill_block(
    llm: LLMProvider,
    skills: SkillRegistry,
    segment: Segment,
    block: ComposedBlock,
    *,
    duration_ms: int,
    feedback: str | None = None,
) -> dict[str, Any]:
    """Fill one block's content payload, given how long the scene it belongs to is on screen.

    ``duration_ms`` is a required parameter rather than read off ``segment.duration_ms`` inside
    this function -- Invariant 1's structural enforcement, unchanged from before T18B: a caller
    who has not measured yet cannot satisfy this signature without inventing a number in plain
    sight.

    ``feedback`` (T18I), when given, is a corrective note appended after the base prompt -- the
    same "## Revise" appendix shape ``visual_plan.py``'s own single re-ask already uses, reused
    here by ``core/graph/nodes/scene_reauthor.py`` for its one bounded re-author attempt after a
    geometry finding names this block's content as too large for the frame.

    The returned dict is ``block_schema_for(block.block_type)``'s own ``model_dump()`` -- it is
    stored on that block's ``payload`` inside ``Segment.scene``, which is untyped (D29), so
    validate it back through ``block_schema_for`` at the point of use rather than trusting the
    dict's shape.
    """
    step_prompt = await load_step_prompt(skills, SCENE_AUTHORING_PACK)
    # Seconds, not milliseconds: the pack's density rules are written as thresholds in seconds
    # ("under 12 seconds", "12 to 30 seconds"), so this is the unit it reasons in.
    prompt = (
        f"{step_prompt.step}\n\n"
        f"Block type: {block.block_type.value}\n"
        f"This block's role in the scene: {block.role}\n"
        f"Measured narration duration: {duration_ms / 1000:.1f} seconds\n"
        f"Segment title: {segment.title}\n"
        f"Narration this scene accompanies:\n{segment.narration}"
    )
    if feedback:
        prompt = f"{prompt}\n\n{feedback}"
    payload = await generate_with_bounded_retries(
        llm,
        prompt,
        block_schema_for(block.block_type),
        system=step_prompt.house_style,
    )
    return normalize_block_payload(block.block_type, payload.model_dump())


async def author_scene(state: SegmentTask, runtime: Runtime[GraphContext]) -> dict:
    """Fill every block in one segment's already-planned scene and return it with each block's
    ``payload`` set.

    One task per segment in the fan-out that follows ``plan_visuals``. Registered with
    ``build_transient_retry_policy()``, never ``build_retry_policies()`` -- ``fill_block``
    isolates its own ``StructuredOutputError`` retries per call, and a node-level policy that
    also matched that error would let an exhausted local retry re-trigger a whole-node redo
    (D73) -- redoing every other block's already-filled content along with it.
    ``author_annotations`` (called after every block is filled) isolates its own budget the same
    way.

    Raises:
        ValueError: the segment has no measured duration, or no scene plan. Unreachable while
            ``assign_tiers``/``plan_visuals`` sit between the earlier fan-outs and this one --
            exists so that reordering the graph fails loudly here instead of quietly authoring a
            scene against an invented duration or an absent plan.
    """
    segment = state["segment"]
    if segment.duration_ms is None:
        raise ValueError(
            f"segment {segment.index} has no measured duration_ms, so its scene cannot be "
            "authored. Scene authoring runs *after* narration is synthesised and measured "
            "(Invariant 1) -- how much text fits on screen is a function of how long it is up."
        )
    if segment.scene is None:
        raise ValueError(
            f"segment {segment.index} has no scene plan, so its blocks cannot be filled. "
            "Scene authoring runs *after* plan_visuals, which decides layout and block types "
            "before any block's content is filled."
        )

    scene = ComposedScene.model_validate(segment.scene)
    # T18I: resume idempotency -- a segment already fully authored in a previous run of this SAME
    # job_id (a checkpoint resume) has every block's payload already set. Without this, a resumed
    # job re-authors from scratch: real LLM spend, and (via sampling non-determinism) DIFFERENT
    # content than the attempt that already rendered cleanly -- exactly what the handoff's own
    # "resume doesn't actually skip ahead" gotcha named. A partially-authored scene (some blocks
    # filled, one not -- unreachable today since fill_block calls run together via gather, but not
    # a state this guard should silently paper over) still falls through to a full re-author below.
    if scene.blocks and all(block.payload is not None for block in scene.blocks):
        return {"segments": {segment.index: segment}}

    payloads = await asyncio.gather(
        *(
            fill_block(
                runtime.context.llm,
                runtime.context.skills,
                segment,
                block,
                duration_ms=segment.duration_ms,
            )
            for block in scene.blocks
        )
    )
    filled_blocks = [
        block.model_copy(update={"payload": payload})
        for block, payload in zip(scene.blocks, payloads, strict=True)
    ]
    annotations = await author_annotations(
        runtime.context.llm, runtime.context.skills, segment, filled_blocks
    )
    filled_scene = scene.model_copy(update={"blocks": filled_blocks, "annotations": annotations})
    return {
        "segments": {segment.index: segment.model_copy(update={"scene": filled_scene.model_dump()})}
    }
