"""The annotation-authoring call: runs after ``core/graph/nodes/scene_author.py`` fills every
block in a scene, so it can name a real item to mark rather than being asked before content
exists (T18D's catalog: every annotation's ``target_item_index`` came back null under the old
``plan_visuals``-time ordering -- D121/D122).
"""

from core.annotation_plan_schema import SceneAnnotations
from core.block_items import item_labels
from core.graph.nodes.skill_prompt import load_step_prompt
from core.graph.nodes.structured_retry import generate_with_bounded_retries
from core.models import Segment
from core.scene_schemas import ComposedAnnotation, ComposedBlock
from interfaces import LLMProvider, SkillRegistry

ANNOTATION_AUTHORING_PACK = "annotation-authoring"


def _describe_block(index: int, block: ComposedBlock) -> str:
    labels = item_labels(block.block_type.value, block.payload or {})
    if not labels:
        return f"Block {index} ({block.block_type.value}): {block.role} -- no numbered items."
    numbered = "\n".join(f"  [{i}] {label}" for i, label in enumerate(labels))
    return f"Block {index} ({block.block_type.value}): {block.role}\n{numbered}"


def _build_prompt(step: str, segment: Segment, blocks: list[ComposedBlock]) -> str:
    lines = [step, "", f"Narration:\n{segment.narration}", "", "## Blocks in this scene"]
    lines.extend(_describe_block(i, block) for i, block in enumerate(blocks))
    return "\n\n".join(lines)


async def author_annotations(
    llm: LLMProvider, skills: SkillRegistry, segment: Segment, blocks: list[ComposedBlock]
) -> list[ComposedAnnotation]:
    """Annotations for one already-filled scene, each naming a real block/item index -- or none,
    which is the common case (the runtime skill pack's own "sparingly" guidance)."""
    step_prompt = await load_step_prompt(skills, ANNOTATION_AUTHORING_PACK)
    prompt = _build_prompt(step_prompt.step, segment, blocks)
    plan = await generate_with_bounded_retries(
        llm, prompt, SceneAnnotations, system=step_prompt.house_style
    )
    return [
        ComposedAnnotation(
            annotation_type=a.annotation_type,
            target_block_index=a.target_block_index,
            target_item_index=a.target_item_index,
            anchor_phrase=a.anchor_phrase,
            caption=a.caption,
        )
        for a in plan.annotations
    ]
