"""What a segment's scene *is*, once planned and (eventually) filled.

Plain ``BaseModel``, never a ``StrictSchema`` -- this is never sent to Azure as a generation
schema, it is what ``Segment.scene`` holds after ``core.scene_plan_schema.VideoScenePlan`` (the
plan) and ``core/graph/nodes/scene_author.py::fill_block`` (the content, one call per block)
have both had their say. ``Segment.scene`` stores this untyped, as ``model_dump()`` -- the same
D29 pattern ``slots`` used before it -- so validate with ``ComposedScene.model_validate`` at the
point of use rather than trusting the dict's shape.

``ComposedBlock.payload`` is deliberately nullable: ``core/graph/nodes/visual_plan.py`` writes
a scene with every block's payload still ``None``, and ``core/graph/nodes/scene_author.py``
fills them in one at a time. A scene mid-authoring is a real, valid state of this type, not an
error -- the same "progressive" shape ``Segment`` itself has always had (D28's docstring: the
nullable fields fill in stages).
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from core.block_types import BlockType, MotifName, SceneLayout


class ComposedBlock(BaseModel):
    """One block in a scene: what it is, why it is there, and its content once filled."""

    model_config = ConfigDict(extra="forbid")

    block_type: BlockType
    role: str
    anchor_phrase: str | None
    payload: dict[str, Any] | None = Field(
        default=None,
        description="This block's content, matching core.block_schemas.block_schema_for"
        "(block_type). Null until core/graph/nodes/scene_author.py fills it.",
    )


class ComposedScene(BaseModel):
    """One segment's whole scene: the video's motif, a layout, and the blocks that fill it."""

    model_config = ConfigDict(extra="forbid")

    motif: MotifName
    layout: SceneLayout
    blocks: list[ComposedBlock]
    continues_previous: bool
