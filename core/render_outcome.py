"""What happened when one segment's composition failed geometry validation and the pipeline had
to do something about it, rather than crash the whole job. T18I's production failure story: kept
separate from ``core/models.py`` (at 187 lines already, and this is a genuinely separate concern
-- a segment's OWN content vs. what the render PIPELINE had to do to cope with it) the same way
``core/scene_schemas.py`` is kept separate from ``core/models.py`` (D28's reasoning, applied
again).

Read by ``core/graph/nodes/finalize.py`` (collected onto ``VideoJob.degraded_segments``) and
printed by ``cli.py``'s own summary -- this is the "which segment, on which finding, not just the
job failed" signal the user asked for directly, after T18H's own gate was found to have none.
"""

from pydantic import BaseModel, ConfigDict


class RenderOutcome(BaseModel):
    """One segment's own render history: how many attempts it took, what geometry findings fired
    along the way, and whether re-authoring or the safe fallback ended up doing the work.

    A segment with no ``RenderOutcome`` at all (the common case) rendered clean on the first
    attempt -- there is deliberately no "success" variant of this type; its ABSENCE from
    ``VideoJob.degraded_segments`` already says that.
    """

    model_config = ConfigDict(extra="forbid")

    segment_index: int
    attempts: int
    finding_codes: list[str]
    reauthored: bool
    fallback_used: bool
