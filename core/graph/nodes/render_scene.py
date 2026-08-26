"""The third fan-out: render one segment's scene, mux its narration onto it, and persist the
result. Runs after ``author_scene`` (via the ``collect_scenes`` join in ``pipeline.py``), since it
needs ``slots`` filled and ``tier`` assigned -- both present by then.

Ties together T17's ``rendering/render_segment.py`` (compose, lint, dispatch by tier -- silent)
and T18's ``mux/audio_mux.py`` (narration on top), the same way ``synthesize_segment`` ties
``TTSProvider`` to ``Storage``.
"""

from pathlib import Path

from langgraph.runtime import Runtime

from core.graph.context import GraphContext
from core.graph.nodes.synthesize import local_narration_path
from core.graph.state import SegmentTask
from mux.audio_mux import mux_audio
from rendering.render_segment import render_segment

# {job_id}/segments/{index}/clip.mp4 -- the segment's final, audible clip. Sibling to
# synthesize.py's SEGMENT_AUDIO_KEY; each producing node owns the key format for what it makes.
SEGMENT_CLIP_KEY = "{job_id}/segments/{index}/clip.mp4"


def local_clip_path(working_dir: Path, job_id: str, index: int) -> Path:
    """Where this segment's final (video + audio) clip lives locally.

    Shared with ``core/graph/nodes/finalize.py``, which reconstructs this same path for every
    segment to concat them -- same reasoning as ``synthesize.local_narration_path``: one
    definition, reused directly against a still-warm local disk rather than round-tripped
    through ``Storage``.
    """
    return working_dir / job_id / "segments" / str(index) / "clip.mp4"


async def render_scene(state: SegmentTask, runtime: Runtime[GraphContext]) -> dict:
    """Render, mux, and persist one segment's clip. Returns it with ``clip_key`` filled in.

    One task per segment in the fan-out that follows ``author_scene``. Registered with
    ``build_transient_retry_policy()`` in ``pipeline.py`` -- this node makes no ``LLMProvider``
    call, so there is no ``StructuredOutputError`` to isolate, only ``RenderFailed`` (retryable)
    and ``CompositionInvalid`` (our own gate, not retryable -- matches neither policy and
    propagates on the first attempt, same as everywhere else it is raised).
    """
    context = runtime.context
    job_id = state["job_id"]
    segment = state["segment"]

    segment_dir = context.working_dir / job_id / "segments" / str(segment.index)
    silent = segment_dir / "silent.mp4"
    await render_segment(
        segment,
        context.render,
        composition_dir=segment_dir / "composition",
        dest=silent,
        fps=context.fps,
        job_id=job_id,
    )

    narration = local_narration_path(context.working_dir, job_id, segment.index)
    clip = local_clip_path(context.working_dir, job_id, segment.index)
    await mux_audio(silent, narration, clip, duration_ms=segment.duration_ms)

    key = SEGMENT_CLIP_KEY.format(job_id=job_id, index=segment.index)
    await context.storage.put_file(key, clip, content_type="video/mp4")

    updated = segment.model_copy(update={"clip_key": key})
    return {"segments": {segment.index: updated}}
