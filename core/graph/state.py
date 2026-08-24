"""The graph's channels, and the one payload shape a ``Send`` task carries.

``segments`` needs a reducer because per-segment fan-out writes to it concurrently within one
superstep -- every ``synthesize_segment`` task returns its own ``{index: Segment}`` update in the
same step, and LangGraph refuses two concurrent writes to a channel with no way to combine them.
A plain dict is keyed by segment index precisely so ``merge_segments`` never has to choose between
two segments: each task only ever contributes the one key it owns.
"""

from typing import Annotated, TypedDict

from core.models import Segment, VideoJob


def merge_segments(existing: dict[int, Segment], update: dict[int, Segment]) -> dict[int, Segment]:
    """Combine two segment-index maps. Later values win on a repeated key, which never happens
    in practice -- each fan-out task owns exactly one index -- but a plain merge is simpler than
    a merge that asserts disjointness for a case the graph shape already rules out."""
    return {**existing, **update}


class GraphState(TypedDict):
    """The whole run's state, and what gets checkpointed after every superstep."""

    job: VideoJob
    segments: Annotated[dict[int, Segment], merge_segments]


class SegmentTask(TypedDict):
    """What one ``Send`` task carries -- one segment's worth of work, plus the job id it belongs
    to (segment paths are scoped per job).

    Shared by both fan-outs: ``synthesize_segment`` and ``author_scene`` want the same thing, one
    segment, and only differ in how far along that segment is when they get it. ``author_scene``
    never uses ``job_id`` -- it writes no files -- but a near-duplicate TypedDict differing by one
    unused field would cost more than it explains.
    """

    job_id: str
    segment: Segment
