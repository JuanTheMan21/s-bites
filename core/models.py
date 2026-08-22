"""The vocabulary the pipeline speaks: what a job is, what a segment is, what a tier is.

Pipeline state and the enums it is built from. What the *LLM* returns lives one module over
in ``core/outline_schema.py`` -- the split is Invariant 1, and ``Segment`` explains it.

stdlib and pydantic only. ``core/tier_resolver.py`` may import nothing but stdlib and this
module, so anything added here that reaches outside the process breaks T5's definition of done
as well as the boundary rule.
"""

from datetime import UTC, datetime
from enum import IntEnum, StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

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


# Each member needs a slot schema in ``core/slot_schemas.py`` and, from T17, a Jinja template in
# ``rendering/templates/``. A member added without both leaves a gap that surfaces at render
# time, minutes into a job, on one particular topic -- which is why ``/newintent`` touches every
# registration point at once.
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


class JobStatus(StrEnum):
    """Where a job is. ``FAILED`` is terminal only until T22 resumes it from its checkpoint."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class Segment(BaseModel):
    """A segment as the pipeline knows it: the plan, plus everything measured since.

    The nullable fields fill in stages, and the order is load-bearing. ``narration`` arrives
    from the scripting node, ``duration_ms`` from the TTS adapter *measuring the audio it just
    wrote*, and only then can ``tier`` be assigned and ``slots`` authored against a real
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
    tier: Tier | None = Field(
        default=None,
        description="Assigned by core/tier_resolver.py, once duration_ms is known.",
    )
    slots: dict[str, Any] | None = Field(
        default=None,
        description="The filled slot payload for this segment's visual intent. Untyped here "
        "because the shape varies by intent; validate it with "
        "core.slot_schemas.slot_schema_for(visual_intent).",
    )


class VideoJob(BaseModel):
    """One video request, and everything the pipeline has learned about it.

    Serves as pipeline state, as the LangGraph checkpoint payload (T14), and as the API
    response body (T19) -- hence a plain model with defaults rather than a strict schema.
    Extras are forbidden all the same: pydantic ignores an unknown key by default, so a typo in
    a request body would be dropped in silence rather than rejected.
    """

    model_config = ConfigDict(extra="forbid")

    job_id: str
    topic: str = Field(description="The prompt as the user typed it.")
    target_duration_ms: int = DEFAULT_TARGET_DURATION_MS
    status: JobStatus = JobStatus.QUEUED
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    segments: list[Segment] = Field(default_factory=list)

    @property
    def segment_count(self) -> int:
        """How many segments this job's target length calls for.

        Derived, deliberately. A ``SEGMENT_COUNT = 15`` in the outline node reads fine until
        someone asks for a ten-minute video and gets a seven-minute one made of longer
        segments. Target length is a parameter of the request, so segment count is a function
        of it.
        """
        return max(MIN_SEGMENTS, round(self.target_duration_ms / 1000 / SECONDS_PER_SEGMENT))
