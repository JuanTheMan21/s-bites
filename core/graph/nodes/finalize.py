"""Closes the run out: concat every segment's rendered+muxed clip into the final video, persist
it, and fold ``segments`` back onto the job.

Runs once, after the ``render_scene`` fan-out has fully converged -- the same "join after a
fan-out" position ``assign_tiers`` occupies between the first two fan-outs, except this join's
work (concat) genuinely needs every segment's finished clip rather than being structurally
required the way ``collect_scenes`` is.

T18K/D162: ``core/graph/node_timing.py::timed`` already logs this whole node's start/elapsed
time, but that measured 53% of total wall clock on a short job with no way to see which of the
four steps below it actually was -- an unconfirmed 2m44s gap around the ``.srt`` write on that
same job (6s on a 15-segment job) is the specific anomaly this per-step instrumentation exists to
either confirm or kill, not guess at.
"""

import logging
import time

from langgraph.runtime import Runtime

from core.graph.context import GraphContext
from core.graph.nodes.render_scene import local_clip_path
from core.graph.state import GraphState
from core.video_job import JobStatus
from mux.concat_segments import concat_segments
from mux.subtitles import write_srt

logger = logging.getLogger(__name__)

# {job_id}/final.mp4 -- sibling to synthesize.py's SEGMENT_AUDIO_KEY and render_scene.py's
# SEGMENT_CLIP_KEY; this is the node that produces the final video, so it owns this key.
FINAL_VIDEO_KEY = "{job_id}/final.mp4"
# T18A: the SRT sidecar. Same offsets as the video/audio it accompanies since concat_segments'
# audio track is a plain unshrunk concat (D93) -- no crossfade arithmetic for subtitles to redo.
FINAL_SUBTITLES_KEY = "{job_id}/final.srt"


async def finalize(state: GraphState, runtime: Runtime[GraphContext]) -> dict:
    """Concat every segment's clip in index order, persist the result, and mark the job done.

    Runs only once every fan-out task has converged on this node, so every segment's ``clip_key``
    is set by construction -- there is nothing here to check for.
    """
    context = runtime.context
    job = state["job"]
    ordered = [state["segments"][i] for i in sorted(state["segments"])]

    clips = [local_clip_path(context.working_dir, job.job_id, segment.index) for segment in ordered]
    durations_ms = [segment.duration_ms for segment in ordered]
    dest = context.working_dir / job.job_id / "final.mp4"

    started = time.perf_counter()
    await concat_segments(clips, dest, durations_ms=durations_ms)
    logger.info("finalize: concat_segments took %.2fs", time.perf_counter() - started)

    key = FINAL_VIDEO_KEY.format(job_id=job.job_id)
    started = time.perf_counter()
    await context.storage.put_file(key, dest, content_type="video/mp4")
    logger.info("finalize: final.mp4 upload took %.2fs", time.perf_counter() - started)

    srt_dest = context.working_dir / job.job_id / "final.srt"
    started = time.perf_counter()
    write_srt(ordered, srt_dest)
    logger.info("finalize: write_srt took %.2fs", time.perf_counter() - started)

    subtitles_key = FINAL_SUBTITLES_KEY.format(job_id=job.job_id)
    started = time.perf_counter()
    await context.storage.put_file(subtitles_key, srt_dest, content_type="text/plain")
    logger.info("finalize: final.srt upload took %.2fs", time.perf_counter() - started)

    # T18I: every segment that needed a re-author, a fallback, or both -- the production-facing
    # signal this pipeline previously had none of beyond a crash. status stays SUCCEEDED
    # regardless: a degraded segment still produced a usable video, and this list is what says
    # the story isn't quite that simple, not a reason to call the whole job failed.
    degraded = [s.render_outcome for s in ordered if s.render_outcome is not None]

    updated_job = job.model_copy(
        update={
            "segments": ordered,
            "status": JobStatus.SUCCEEDED,
            "video_key": key,
            "subtitles_key": subtitles_key,
            "degraded_segments": degraded,
        }
    )
    return {"job": updated_job}
