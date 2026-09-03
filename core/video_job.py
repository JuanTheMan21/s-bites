"""What a job is -- one video request, and everything the pipeline has learned about it.

Split out of ``core/models.py`` (T18I, to stay under the 200-line ceiling once that module grew
``Segment.render_outcome``): a genuinely separate concern (the whole run) from ``core/models.py``'s
own (one segment), the same way ``core/scene_schemas.py`` is kept separate from ``core/models.py``
(D28's reasoning, applied again). stdlib and pydantic only, same rule as ``core/models.py``.
"""

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from core.models import DEFAULT_TARGET_DURATION_MS, MIN_SEGMENTS, SECONDS_PER_SEGMENT, Segment
from core.render_outcome import RenderOutcome


class JobStatus(StrEnum):
    """Where a job is. ``FAILED`` is terminal only until T22 resumes it from its checkpoint."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


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
    video_key: str | None = Field(
        default=None,
        description="Storage key of the finished, concatenated video. Set only by "
        "core/graph/nodes/finalize.py, once every segment's clip has been rendered and muxed.",
    )
    subtitles_key: str | None = Field(
        default=None,
        description="T18A: storage key of the SRT sidecar (mux/subtitles.py). Set alongside "
        "video_key by core/graph/nodes/finalize.py. May stay null on the same terms as an "
        "individual segment's word_marks -- nothing downstream requires it.",
    )
    degraded_segments: list[RenderOutcome] = Field(
        default_factory=list,
        description="T18I: every segment whose render needed a re-author, a fallback, or both, "
        "collected by core/graph/nodes/finalize.py from each segment's own render_outcome. Empty "
        "means every segment rendered clean on the first attempt. status stays SUCCEEDED even "
        "when this is non-empty -- a degraded segment still produced a usable video; this is the "
        "signal that says so isn't the whole story, not a reason to call the job failed.",
    )

    @property
    def segment_count(self) -> int:
        """How many segments this job's target length calls for.

        Derived, deliberately. A ``SEGMENT_COUNT = 15`` in the outline node reads fine until
        someone asks for a ten-minute video and gets a seven-minute one made of longer
        segments. Target length is a parameter of the request, so segment count is a function
        of it.
        """
        return max(MIN_SEGMENTS, round(self.target_duration_ms / 1000 / SECONDS_PER_SEGMENT))
