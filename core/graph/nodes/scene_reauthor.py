"""One bounded re-authoring attempt for a scene whose composition failed geometry validation with
a content-shaped finding (``rendering/geometry_findings.py::is_content_retryable``).

**A narrow, explicit exception to D2's "no repair loop" stance, not a silent override of it.**
D2 rejected the LLM writing HTML directly, judged and re-rolled by a lint loop -- the LLM never
does that here either. What changed is that ``validate_geometry`` (T18H) can now say a block's
*content* (too many items, too long a caption) didn't fit the frame, a judgement only a fresh
authoring pass can act on and that no static schema constraint can express. This module re-runs
exactly the same calls ``scene_author.py``/``annotation_author.py`` already make for the first
attempt, with the concrete failure fed back as feedback -- never a second, different mechanism.
Bounded to ONE attempt, the same single-corrective-re-ask shape ``core/graph/nodes/
visual_plan.py`` already uses for ``missed_block_opportunities``.
"""

import asyncio

from core.graph.nodes.annotation_author import author_annotations
from core.graph.nodes.scene_author import fill_block
from core.models import Segment
from core.scene_schemas import ComposedScene
from interfaces import LLMProvider, SkillRegistry


async def reauthor_scene(
    llm: LLMProvider,
    skills: SkillRegistry,
    segment: Segment,
    scene: ComposedScene,
    *,
    feedback: str,
) -> ComposedScene:
    """Re-fill every block in ``scene`` (same block/layout shape, new content) and re-author
    annotations against the result, with ``feedback`` -- naming exactly what overflowed --
    appended to every block's own authoring prompt."""
    payloads = await asyncio.gather(
        *(
            fill_block(
                llm, skills, segment, block, duration_ms=segment.duration_ms, feedback=feedback
            )
            for block in scene.blocks
        )
    )
    filled_blocks = [
        block.model_copy(update={"payload": payload})
        for block, payload in zip(scene.blocks, payloads, strict=True)
    ]
    annotations = await author_annotations(llm, skills, segment, filled_blocks)
    return scene.model_copy(update={"blocks": filled_blocks, "annotations": annotations})
