"""The third fan-out: render one segment's scene, mux its narration onto it, and persist the
result. Runs after ``author_scene`` (via the ``collect_scenes`` join in ``pipeline.py``), since it
needs ``slots`` filled and ``tier`` assigned -- both present by then.

Ties together T17's ``rendering/render_segment.py`` (compose, lint, dispatch by tier -- silent)
and T18's ``mux/audio_mux.py`` (narration on top), the same way ``synthesize_segment`` ties
``TTSProvider`` to ``Storage``.

T18I: gained a bounded recovery sequence and resume idempotency -- the production failure story
D124 left open. Previously a single ``CompositionInvalid`` here propagated straight through the
graph, killing every other segment's own already-completed work along with it, with nothing
telling anyone which segment or which finding. Now: one geometry failure whose findings are all
content-shaped (``rendering/geometry_findings.py::is_content_retryable``) gets ONE re-authored
retry with the specific findings fed back as feedback; anything else -- a non-content finding, or
a retry that still fails -- falls back to a deterministic, LLM-free title card
(``scene_fallback.py``), so one bad segment degrades rather than sinks the whole ``VideoJob``. Every
deviation from a clean first attempt is both logged loudly (so it cannot go unnoticed the way a
crash used to force attention) and recorded on the segment's own ``render_outcome`` (so it reaches
``VideoJob.degraded_segments`` via ``finalize.py``, not just the console). A genuine template/code
bug is NEVER retried -- see ``geometry_findings.py``'s own docstring for why -- so this cannot mask
the class of defect T18H's gate exists to catch; it only stops one segment's failure from taking
fourteen others down with it.
"""

import logging
from pathlib import Path

from langgraph.runtime import Runtime

from core.graph.context import GraphContext
from core.graph.nodes.scene_fallback import title_card_scene
from core.graph.nodes.scene_reauthor import reauthor_scene
from core.graph.nodes.synthesize import local_narration_path
from core.graph.state import SegmentTask
from core.models import Segment
from core.render_outcome import RenderOutcome
from core.scene_schemas import ComposedScene
from interfaces import CompositionInvalid
from mux.audio_mux import mux_audio
from rendering.geometry_findings import feedback_note, finding_codes, is_content_retryable
from rendering.render_segment import render_segment

logger = logging.getLogger(__name__)

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


async def _render(
    segment: Segment, context: GraphContext, composition_dir: Path, dest: Path
) -> None:
    await render_segment(
        segment, context.render, composition_dir=composition_dir, dest=dest, fps=context.fps
    )


async def render_scene(state: SegmentTask, runtime: Runtime[GraphContext]) -> dict:
    """Render, mux, and persist one segment's clip. Returns it with ``clip_key`` filled in (and,
    T18I, ``render_outcome`` set if this segment needed more than its first attempt).

    One task per segment in the fan-out that follows ``author_scene``. Registered with
    ``build_transient_retry_policy()`` in ``pipeline.py`` -- this node makes no ``LLMProvider``
    call of its OWN (the bounded re-author below isolates its budget the same way ``author_scene``
    already does), so there is no ``StructuredOutputError`` to isolate at the node level, only
    ``RenderFailed`` (retryable) and a ``CompositionInvalid`` that survives every recovery step
    below (our own gate, not retryable at the node level -- see ``interfaces/errors.py``).
    """
    context = runtime.context
    job_id = state["job_id"]
    segment = state["segment"]

    segment_dir = context.working_dir / job_id / "segments" / str(segment.index)
    composition_dir = segment_dir / "composition"
    silent = segment_dir / "silent.mp4"
    clip = local_clip_path(context.working_dir, job_id, segment.index)

    # T18I: resume idempotency -- a segment already rendered and muxed in a previous run of this
    # SAME job_id (a checkpoint resume) has clip_key set and its local clip still on disk. Without
    # this, a resumed job re-renders and re-muxes work already done, the render-side half of the
    # same "resume doesn't actually skip ahead" gap author_scene.py's own guard closes for
    # authoring -- this is what turns LangGraph's per-superstep checkpoint into the segment-level
    # retry the production failure story needs.
    if segment.clip_key is not None and clip.exists():
        return {"segments": {segment.index: segment}}

    scene = ComposedScene.model_validate(segment.scene)
    codes: list[str] = []
    reauthored = False
    fallback_used = False
    attempts = 1

    try:
        await _render(segment, context, composition_dir, silent)
    except CompositionInvalid as exc:
        codes = finding_codes(exc.findings)
        if is_content_retryable(exc.findings):
            logger.warning(
                "segment %s: geometry validation failed with content-shaped findings %s -- "
                "re-authoring this scene once with the failure fed back as feedback",
                segment.index,
                codes,
            )
            reauthored = True
            attempts += 1
            reauthored_scene = await reauthor_scene(
                context.llm, context.skills, segment, scene, feedback=feedback_note(exc.findings)
            )
            segment = segment.model_copy(update={"scene": reauthored_scene.model_dump()})
            try:
                await _render(segment, context, composition_dir, silent)
            except CompositionInvalid as exc2:
                codes = codes + finding_codes(exc2.findings)
                fallback_used = True
        else:
            fallback_used = True

        if fallback_used:
            logger.warning(
                "segment %s: falling back to a plain title card after findings %s -- this "
                "segment's video is degraded; see VideoJob.degraded_segments",
                segment.index,
                codes,
            )
            attempts += 1
            fallback_scene = title_card_scene(segment, scene.motif)
            segment = segment.model_copy(update={"scene": fallback_scene.model_dump()})
            # Deliberately unguarded: if even the deterministic title card fails geometry
            # validation, that is a genuine bug in our own templates (TITLE is the simplest block
            # in the library), not a content problem -- it should propagate and be loud, not be
            # swallowed by a third recovery step.
            await _render(segment, context, composition_dir, silent)

    narration = local_narration_path(context.working_dir, job_id, segment.index)
    await mux_audio(silent, narration, clip, duration_ms=segment.duration_ms)

    key = SEGMENT_CLIP_KEY.format(job_id=job_id, index=segment.index)
    await context.storage.put_file(key, clip, content_type="video/mp4")

    render_outcome = (
        RenderOutcome(
            segment_index=segment.index,
            attempts=attempts,
            finding_codes=codes,
            reauthored=reauthored,
            fallback_used=fallback_used,
        )
        if attempts > 1
        else None
    )
    updated = segment.model_copy(update={"clip_key": key, "render_outcome": render_outcome})
    return {"segments": {segment.index: updated}}
