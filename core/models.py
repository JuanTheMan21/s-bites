"""The vocabulary the pipeline speaks: what a segment is, what a tier is.

Pipeline state and the enums it is built from. What the *LLM* returns lives one module over
in ``core/outline_schema.py`` -- the split is Invariant 1, and ``Segment`` explains it.
``VideoJob``/``JobStatus`` live in ``core/video_job.py`` -- split out once ``Segment`` grew
``render_outcome`` and this file hit the 200-line ceiling, the same way ``core/scene_schemas.py``
is kept separate from this module (D28's reasoning, applied again): a genuinely separate concern
(the whole run) from this module's own (one segment). Importers of ``VideoJob``/``JobStatus``
(``api/``, ``cli.py``) get them from ``core.video_job`` now, not from here.

stdlib and pydantic only. ``core/tier_resolver.py`` may import nothing but stdlib and this
module, so anything added here that reaches outside the process breaks T5's definition of done
as well as the boundary rule.
"""

from enum import IntEnum, StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from core.render_outcome import RenderOutcome
from core.synthesis import WordMark

# Narration pace. The one number that turns a requested video length into a segment count, so
# 7 minutes yields ~15 segments and 10 minutes yields ~21 without either figure being written
# down anywhere as a constant.
SECONDS_PER_SEGMENT = 28

# A video still needs an opening, a middle, and a close.
MIN_SEGMENTS = 3

# The default *for the parameter* -- not an assumption anything downstream may make.
DEFAULT_TARGET_DURATION_MS = 7 * 60 * 1000


class Tier(IntEnum):
    """How richly a segment is rendered, and therefore what it costs in frames.

    ``IntEnum`` because the tier resolver compares and sums these, and a checkpointed job
    serialises them as 0/1/2. The names say what happens; the values are the tier numbers used
    everywhere else. Capture method per tier is in the ``scene-templates`` skill.
    """

    STATIC = 0
    REVEAL = 1
    ANIMATED = 2


# T18B: no longer a template-selection key -- ``rendering/compose.py`` dispatches by
# ``SceneLayout``/``BlockType`` now, not by this enum. This is a coarse, outline-time hint the
# LLM fills before the real narration exists; ``core/block_types.py::ALLOWED_BLOCKS`` documents
# what each member typically becomes, and ``plan_visuals`` (``core/graph/nodes/visual_plan.py``)
# is free to choose differently once it has the actual narration in hand. A member added here
# needs an ``ALLOWED_BLOCKS`` entry and a line in ``runtime_skills/outline/1.0.md``'s table --
# nothing under ``rendering/`` -- see ``/newintent`` for the (now much shorter) registration list,
# or ``/newblock`` if what's actually needed is a new ``BlockType``, which is the common case.
#
# The docstring stays one line on purpose: pydantic copies it into the JSON Schema, so it is
# sent to the model on every call. Rationale for us belongs up here, where it costs no tokens.
class VisualIntent(StrEnum):
    """What a segment's visual is for. Closed by design."""

    TITLE_CARD = "title_card"
    BULLET_LIST = "bullet_list"
    COMPARISON = "comparison"
    DIAGRAM_FLOW = "diagram_flow"
    CODE_WALKTHROUGH = "code_walkthrough"
    STAT_CALLOUT = "stat_callout"


# The tier resolver ranks by importance when spending a fixed frame budget, so this is what
# decides which few scenes get animated.
#
# An enum rather than an ``int`` with ``ge=1, le=5`` because strict mode drops range keywords:
# those bounds would be silently absent from the schema Azure enforces, and the model would be
# free to answer 47. ``enum`` is on the supported list, so the constraint survives into the
# generation constraint itself. Same one-line-docstring rule as VisualIntent above.
class Importance(IntEnum):
    """How much a segment matters, 1 (aside) to 5 (the point of the video)."""

    ASIDE = 1
    MINOR = 2
    NORMAL = 3
    MAJOR = 4
    CRITICAL = 5


class Segment(BaseModel):
    """A segment as the pipeline knows it: the plan, plus everything measured since.

    The nullable fields fill in stages, and the order is load-bearing. ``narration`` arrives
    from the scripting node, ``duration_ms`` from the TTS adapter *measuring the audio it just
    wrote*, and only then can ``tier`` be assigned and ``scene`` authored against a real
    duration.

    That ordering is Invariant 1, and it is why this is a separate class rather than
    ``SegmentPlan`` with more fields: a combined model would show the LLM a ``duration_ms``
    field it is forbidden to fill, leaving the rule to be enforced by prompt wording. Here the
    model never sees the field at all.
    """

    model_config = ConfigDict(extra="forbid")

    index: int = Field(description="Position in the video, from 0.")
    title: str
    summary: str
    visual_intent: VisualIntent
    importance: Importance

    narration: str | None = Field(
        default=None, description="The spoken script for this segment, written by T15."
    )
    duration_ms: int | None = Field(
        default=None,
        description="Measured length of the narration audio, in milliseconds. Set only by a "
        "TTSProvider from the file it wrote -- never estimated, never from a word count.",
    )
    word_marks: list[WordMark] = Field(
        default_factory=list,
        description="T18A: per-word timing within this segment's narration audio, filled at "
        "the same stage as duration_ms. May be empty -- not every TTSProvider reports word "
        "boundaries; consumers must degrade to an even stagger rather than assume this is set.",
    )
    tier: Tier | None = Field(
        default=None,
        description="Assigned by core/tier_resolver.py, once duration_ms is known.",
    )
    scene: dict[str, Any] | None = Field(
        default=None,
        description="This segment's composed scene: a layout plus the blocks that fill it. "
        "Untyped here for the same reason `slots` was before it -- the shape is progressive "
        "(core/graph/nodes/visual_plan.py writes it with each block's payload still null, "
        "core/graph/nodes/scene_author.py fills them in) and varies with the layout/block "
        "choice, which the LLM makes per video rather than per intent now. Validate with "
        "core.scene_schemas.ComposedScene at the point of use.",
    )
    clip_key: str | None = Field(
        default=None,
        description="Storage key of this segment's final clip (rendered video + narration "
        "audio, muxed). Set only by core/graph/nodes/render_scene.py, once slots are filled.",
    )
    render_outcome: RenderOutcome | None = Field(
        default=None,
        description="T18I: set only when this segment's render needed more than one attempt -- "
        "a re-author, a fallback to a plain title card, or both. Null is the common case (clean "
        "on the first try) and is not itself a RenderOutcome variant; see that type's docstring.",
    )
