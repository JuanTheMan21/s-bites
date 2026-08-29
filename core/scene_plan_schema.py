"""What the LLM returns when asked to plan a whole video's visuals in one call.

Routes around D29 (Azure strict structured output cannot express a discriminated union) by
never asking for one: ``VideoScenePlan`` names *which* blocks each segment gets as a flat list
of a plain enum (``BlockType`` -- enums survive strict mode, unions do not, per D27's
precedent), never their content. Content is a second, separate call per block
(``core/graph/nodes/scene_author.py::fill_block``), each constrained to that one block's own
concrete schema. Two calls per block-bearing segment instead of one call with a union inside it.

Kept separate from ``core/scene_schemas.py`` the same way ``core/outline_schema.py`` is kept
separate from ``core/models.py`` (D28's reasoning, applied one level down): this is what the LLM
is *asked for* (a plan, still contentless), that is what a segment's scene *is* once filled
(``ComposedScene``, plain ``BaseModel``, never sent to Azure). Two classes, two different rule
sets -- ``StrictSchema`` for this one, defaults and no-repair-loop plumbing for the other.
"""

from pydantic import Field

from core.block_types import AnnotationType, BlockType, MotifName, SceneLayout
from core.strict_schema import StrictSchema


class PlannedAnnotation(StrictSchema):
    """One small overlay mark on an already-planned block -- not yet resolved to a beat.

    Not a ``PlannedBlock``: an annotation targets a specific element inside another block
    (``target_block_index``, optionally ``target_item_index``) rather than filling its own
    layout region -- see ``core/scene_schemas.py::ComposedAnnotation`` for the filled shape and
    ``rendering/annotations.py`` for how a target resolves to a real element id."""

    annotation_type: AnnotationType = Field(
        description="CURSOR points at something. CHECK marks something correct or complete. "
        "WARNING flags something as a problem."
    )
    target_block_index: int = Field(
        description="Which block in this segment's blocks list (0-based) this annotation "
        "attaches to."
    )
    target_item_index: int | None = Field(
        description="Which numbered sub-element of the target block this points at -- e.g. the "
        "third array_grid cell, the second code_diff line, the first graph_diagram node -- "
        "0-based, or null to attach to the block as a whole rather than one of its items."
    )
    anchor_phrase: str | None = Field(
        description="A short phrase copied VERBATIM from this segment's narration, marking the "
        "moment this annotation should appear. Null to appear once the target block has "
        "settled."
    )
    caption: str | None = Field(
        description="A short label shown beside the annotation, e.g. 'off by one' for a "
        "warning -- or null, which is normal for cursor/check."
    )


class PlannedBlock(StrictSchema):
    """One block, chosen for one segment -- not yet filled with content."""

    block_type: BlockType = Field(description="Which block this segment's scene includes.")
    role: str = Field(
        description="A short phrase saying what this block is for in this scene, e.g. 'the "
        "vulnerable query' or 'the two approaches side by side'. Feeds the follow-up call that "
        "fills this block's own content -- it is not shown to the viewer."
    )
    anchor_phrase: str | None = Field(
        description="A short phrase copied VERBATIM from this segment's narration, marking the "
        "moment in the spoken audio this block should appear or change. Null if the block "
        "should simply be present from the scene's start rather than timed to a specific word."
    )


class SegmentScenePlan(StrictSchema):
    """One segment's whole scene, planned: a layout and the blocks that fill it."""

    segment_index: int = Field(description="Which segment this plan is for, matching its index.")
    layout: SceneLayout = Field(
        description="SINGLE for one block filling the frame; SPLIT_HORIZONTAL for exactly two "
        "blocks side by side (the natural shape for a comparison or a code-and-diagram split)."
    )
    blocks: list[PlannedBlock] = Field(
        description="One block for SINGLE, exactly two for SPLIT_HORIZONTAL, in left-to-right "
        "or top-to-bottom order."
    )
    continues_previous: bool = Field(
        description="True if this scene should read as a continuation of the previous "
        "segment's visual rather than a cold, unrelated composition -- e.g. the same diagram "
        "carrying on, or the same array still in view. False for most segments; true only "
        "where the narration itself is picking up where the last segment left off."
    )
    annotations: list[PlannedAnnotation] = Field(
        description="Zero or more small overlay marks on this scene's blocks. Sparingly -- at "
        "most one or two per scene, only where the narration is genuinely pointing something "
        "out. A target_block_index must point at a block within THIS same list, and for a "
        "SPLIT_HORIZONTAL scene must stay within the same panel the annotation is about -- "
        "never a block in the other panel."
    )


class VideoScenePlan(StrictSchema):
    """The whole video's visual plan, one call, every segment at once.

    One call rather than one per segment is what makes variety enforceable at all: nothing
    that only ever sees one segment can know it is about to repeat a block type six times in a
    row, or that the whole video has leaned on one shape. This is also cheaper than the
    per-segment alternative -- one call replaces what would otherwise be one plan call per
    segment on top of the fill calls that already exist.
    """

    motif: MotifName = Field(
        description="One motif for the whole video, chosen to suit the topic -- e.g. Terminal "
        "for a security topic, Blueprint for an architecture or systems topic."
    )
    segments: list[SegmentScenePlan] = Field(
        description="A plan for every segment, in index order. Segment 0's plan is ignored and "
        "overridden with a title card regardless of what is returned here -- do not spend "
        "effort on it."
    )
