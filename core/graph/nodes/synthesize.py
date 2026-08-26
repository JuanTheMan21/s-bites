"""The one node in this skeleton that does real interface work: narrate a segment, measure it,
and persist it. Chosen over an ``LLMProvider`` call for the fan-out demonstration because it is
the only interface with a natural one-call-per-segment shape that needs nothing from T15/T16/T17's
not-yet-built logic to be meaningful -- narration text already exists on the placeholder segment
``plan_segments`` produced.
"""

from pathlib import Path

from langgraph.runtime import Runtime

from core.graph.context import GraphContext
from core.graph.state import SegmentTask

# artifacts/<job>/segments/<n>/narration.wav, per D21 -- the artifact layout is the caller's
# business, not the TTSProvider's.
SEGMENT_AUDIO_KEY = "{job_id}/segments/{index}/narration.wav"


def local_narration_path(working_dir: Path, job_id: str, index: int) -> Path:
    """Where this segment's narration WAV lives locally, before (and after) it is persisted
    through ``Storage``.

    Shared with ``core/graph/nodes/render_scene.py``, which runs in the same process against the
    same ``working_dir`` and needs this exact file to hand to ``mux.audio_mux.mux_audio`` --
    reusing it there avoids a redundant ``Storage.get_file`` round-trip for a file already on
    disk. One definition, so the two can never drift apart (D43/D50's reasoning, applied here).
    """
    return working_dir / job_id / "segments" / str(index) / "narration.wav"


async def synthesize_segment(state: SegmentTask, runtime: Runtime[GraphContext]) -> dict:
    """Narrate ``state["segment"]``, measure the result, and store it.

    Returns a ``{segments: {index: updated_segment}}`` update -- merged into the main state by
    ``core.graph.state.merge_segments``, alongside every other segment's concurrent task in the
    same fan-out.
    """
    context = runtime.context
    segment = state["segment"]
    key = SEGMENT_AUDIO_KEY.format(job_id=state["job_id"], index=segment.index)
    local_path = local_narration_path(context.working_dir, state["job_id"], segment.index)

    _, duration_ms = await context.tts.synthesize(segment.narration, local_path)
    await context.storage.put_file(key, local_path, content_type="audio/wav")

    updated = segment.model_copy(update={"duration_ms": duration_ms})
    return {"segments": {segment.index: updated}}
