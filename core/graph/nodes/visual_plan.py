"""The join node that sees a whole video at once, and decides every segment's scene shape in
one call -- the structural fix for the repetition T18A's real output surfaced (D95: "8 of 15
segments were diagram_flow"). ``author_scene``'s fan-out authors each segment in isolation and
always will; nothing inside a fan-out can know what a sibling task is doing. This runs *before*
that fan-out, once per video, precisely so something in the pipeline finally can.

Sits between ``assign_tiers`` and the ``author_scene`` fan-out in ``core/graph/pipeline.py`` --
after tiers (so the prompt can mention which segments earned the richest rendering), before
scene authoring (so every segment's plan exists before any block's content is filled).
"""

from langgraph.runtime import Runtime

from core.block_triggers import missed_block_opportunities
from core.block_types import ALLOWED_BLOCKS, BlockType, MotifName, SceneLayout
from core.graph.context import GraphContext
from core.graph.nodes.skill_prompt import load_step_prompt
from core.graph.nodes.structured_retry import generate_with_bounded_retries
from core.graph.state import GraphState
from core.models import Segment
from core.scene_normalize import normalize_layout
from core.scene_plan_schema import SegmentScenePlan, VideoScenePlan
from core.scene_schemas import ComposedBlock, ComposedScene
from core.scene_variety import check_variety
from interfaces import LLMProvider, SkillRegistry

VISUAL_PLAN_PACK = "visual-plan"

# The block-vocabulary table appended to the prompt, built once at import time rather than per
# call -- ALLOWED_BLOCKS never changes at runtime.
_BLOCK_GUIDANCE = "\n".join(
    f"- {intent.value}: usually {', '.join(sorted(b.value for b in blocks))}"
    for intent, blocks in ALLOWED_BLOCKS.items()
)


def _forced_title_scene(motif: MotifName) -> ComposedScene:
    """Segment 0's plan, unconditional -- the structural fix for forcing a title card, not an
    advisory line in a prompt. Content is still authored normally by ``fill_block``; only the
    *shape* (one TITLE block, alone) is decided here rather than asked of the LLM."""

    return ComposedScene(
        motif=motif,
        layout=SceneLayout.SINGLE,
        blocks=[
            ComposedBlock(block_type=BlockType.TITLE, role="Opening title", anchor_phrase=None)
        ],
        continues_previous=False,
    )


def _fallback_scene(motif: MotifName) -> ComposedScene:
    """The scene a segment gets if ``VideoScenePlan.segments`` omits its index -- nothing in
    strict-mode structured output can force a list to cover every index (D74's same precedent:
    the outline call is not enforced to return exactly the requested segment count either), so
    this is the defensive default rather than a crash on an incomplete response."""

    return ComposedScene(
        motif=motif,
        layout=SceneLayout.SINGLE,
        blocks=[
            ComposedBlock(
                block_type=BlockType.TEXT_PANEL, role="Fallback content", anchor_phrase=None
            )
        ],
        continues_previous=False,
    )


def _build_prompt(step: str, segments: list[Segment]) -> str:
    lines = [step, "", "## Segments", ""]
    for segment in segments:
        lines.append(
            f"### Segment {segment.index}: {segment.title}\n"
            f"Outline visual intent: {segment.visual_intent.value}\n"
            f"Tier: {segment.tier.name if segment.tier else 'unknown'}\n"
            f"Measured duration: {(segment.duration_ms or 0) / 1000:.1f} seconds\n"
            f"Narration: {segment.narration}\n"
        )
    lines.append("## Typical blocks per outline intent (a hint, not a rule)")
    lines.append(_BLOCK_GUIDANCE)
    return "\n".join(lines)


async def plan_video_visuals(
    llm: LLMProvider, skills: SkillRegistry, segments: list[Segment], *, appendix: str | None = None
) -> VideoScenePlan:
    """One call, every segment's scene shape at once. ``segments`` should be in index order --
    the prompt presents them that way so the model can reason about sequence and repetition.
    ``appendix`` (T18E), when given, is a corrective note appended after the base prompt -- the
    re-ask ``plan_visuals`` makes when ``missed_block_opportunities`` finds something."""
    step_prompt = await load_step_prompt(skills, VISUAL_PLAN_PACK)
    prompt = _build_prompt(step_prompt.step, segments)
    if appendix:
        prompt = f"{prompt}\n\n{appendix}"
    return await generate_with_bounded_retries(
        llm, prompt, VideoScenePlan, system=step_prompt.house_style
    )


def _reask_appendix(
    missed: dict[int, BlockType], variety_violations: list[str], segments: list[Segment]
) -> str:
    by_index = {s.index: s for s in segments}
    lines = ["## Revise"]
    if missed:
        lines.append(
            "These segments' own narration clearly calls for a block type the plan above never "
            "uses anywhere in the video. Keep everything else about your plan; for each segment "
            "named below, make that block type its primary block:"
        )
        lines.extend(
            f"- Segment {index} ({by_index[index].title}): use `{block_type.value}`."
            for index, block_type in missed.items()
        )
    if variety_violations:
        lines.append(
            "The plan above also breaks this video's own variety rules. Fix each of these "
            "while keeping every other segment's plan unchanged:"
        )
        lines.extend(f"- {violation}" for violation in variety_violations)
    return "\n".join(lines)


async def plan_visuals(state: GraphState, runtime: Runtime[GraphContext]) -> dict:
    """Plan every segment's scene shape and return them with ``scene`` set to an unfilled
    ``ComposedScene`` (every block's ``payload`` still ``None``) -- ``author_scene``'s fan-out
    fills each block's content next.

    Registered with ``build_transient_retry_policy()`` alone in ``pipeline.py``, never
    ``build_retry_policies()`` -- this node makes one or two ``LLMProvider`` calls (see below),
    each isolated via ``generate_with_bounded_retries`` (D73's pattern, same as ``plan_segments``
    and ``author_scene``).

    T18E: if the first plan leaves a segment's own narration clearly calling for a block type used
    nowhere in the video (``core/block_triggers.py`` -- T18D's real-render matrix found TIMELINE
    rendered zero times across six topics, D121/D122), this makes exactly ONE bounded re-ask with
    a corrective appendix. T18I folds a second check into that SAME re-ask rather than adding a
    third call: ``core/scene_variety.py`` enforces, in code, the variety rules the skill pack has
    stated in prose since T18C (no block type leading more than a third of the video, no two
    consecutive segments sharing a primary block type) -- a real render surfaced these as still
    routinely broken despite the prose. One appendix can name both kinds of problem at once; the
    second plan is taken as final either way -- no third call, and no deterministic override of
    the model's own choice.
    """
    context = runtime.context
    segments = state["segments"]
    ordered = sorted(segments.values(), key=lambda s: s.index)

    plan = await plan_video_visuals(context.llm, context.skills, ordered)
    missed = missed_block_opportunities(ordered, plan)
    variety_violations = check_variety(plan)
    if missed or variety_violations:
        appendix = _reask_appendix(missed, variety_violations, ordered)
        plan = await plan_video_visuals(context.llm, context.skills, ordered, appendix=appendix)

    by_index: dict[int, SegmentScenePlan] = {p.segment_index: p for p in plan.segments}

    updated: dict[int, Segment] = {}
    for segment in ordered:
        if segment.index == 0:
            scene = _forced_title_scene(plan.motif)
        else:
            segment_plan = by_index.get(segment.index)
            if segment_plan is None:
                scene = _fallback_scene(plan.motif)
            else:
                planned_blocks = [
                    ComposedBlock(
                        block_type=b.block_type, role=b.role, anchor_phrase=b.anchor_phrase
                    )
                    for b in segment_plan.blocks
                ]
                layout, blocks = normalize_layout(segment_plan.layout, planned_blocks)
                scene = ComposedScene(
                    motif=plan.motif,
                    layout=layout,
                    blocks=blocks,
                    continues_previous=segment_plan.continues_previous,
                )
        updated[segment.index] = segment.model_copy(update={"scene": scene.model_dump()})

    return {"segments": updated}
