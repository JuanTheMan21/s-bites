"""What the LLM returns when asked to place annotations on an already-filled scene.

Split from ``core/scene_plan_schema.py`` (T18E, D121/D122): ``plan_visuals`` used to ask for an
annotation's ``target_item_index`` before any block had content to index into, so the model could
only ever answer ``null`` -- T18D's catalog found this in all 20 real annotations sampled. This
call runs from ``core/graph/nodes/annotation_author.py``, after ``core/graph/nodes/
scene_author.py`` fills every block, so it can name a real item.
"""

from pydantic import Field

from core.block_types import AnnotationType
from core.strict_schema import StrictSchema


class AuthoredAnnotation(StrictSchema):
    """One small overlay mark on a block this scene already has real content for."""

    annotation_type: AnnotationType = Field(
        description="CURSOR points at something. CHECK marks something correct or complete. "
        "WARNING flags something as a problem."
    )
    target_block_index: int = Field(
        description="Which block in this segment's blocks list (0-based) this annotation "
        "attaches to. Only a block listed with numbered items below may be targeted."
    )
    target_item_index: int = Field(
        description="Which numbered item of the target block this points at (0-based), matching "
        "one of the numbered items listed for that block -- the third array_grid cell, the "
        "second code_diff line, the first graph_diagram node. Always a real item; never a guess."
    )
    anchor_phrase: str = Field(
        description="A short phrase copied VERBATIM from this segment's narration, marking the "
        "moment this annotation should appear."
    )
    caption: str | None = Field(
        description="A short label shown beside the annotation, e.g. 'off by one' for a "
        "warning -- or null, which is normal for cursor/check."
    )


class SceneAnnotations(StrictSchema):
    """Zero or more annotations for one already-authored scene. Wrapped in an object because a
    strict-mode response root must be an object, never a bare list (``core/strict_schema.py``)."""

    annotations: list[AuthoredAnnotation] = Field(
        description="At most one or two, sparingly -- most scenes should have none. Only where "
        "the narration is genuinely pointing something out."
    )
