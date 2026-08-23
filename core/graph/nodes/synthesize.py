"""The one node in this skeleton that does real interface work: narrate a segment, measure it,
and persist it. Chosen over an ``LLMProvider`` call for the fan-out demonstration because it is
the only interface with a natural one-call-per-segment shape that needs nothing from T15/T16/T17's
not-yet-built logic to be meaningful -- narration text already exists on the placeholder segment
``plan_segments`` produced.
"""

from langgraph.runtime import Runtime

from core.graph.context import GraphContext
from core.graph.state import SegmentTask

# artifacts/<job>/segments/<n>/narration.wav, per D21 -- the artifact layout is the caller's
# business, not the TTSProvider's.
SEGMENT_AUDIO_KEY = "{job_id}/segments/{index}/narration.wav"


async def synthesize_segment(state: SegmentTask, runtime: Runtime[GraphContext]) -> dict:
    """Narrate ``state["segment"]``, measure the result, and store it.

    Returns a ``{segments: {index: updated_segment}}`` update -- merged into the main state by
    ``core.graph.state.merge_segments``, alongside every other segment's concurrent task in the
    same fan-out.
    """
    context = runtime.context
    segment = state["segment"]
    key = SEGMENT_AUDIO_KEY.format(job_id=state["job_id"], index=segment.index)
    local_path = (
        context.working_dir / state["job_id"] / "segments" / str(segment.index) / "narration.wav"
    )

    _, duration_ms = await context.tts.synthesize(segment.narration, local_path)
    await context.storage.put_file(key, local_path, content_type="audio/wav")

    updated = segment.model_copy(update={"duration_ms": duration_ms})
    return {"segments": {segment.index: updated}}
