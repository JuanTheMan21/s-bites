"""Closes the run out: concat every segment's rendered+muxed clip into the final video, persist
it, and fold ``segments`` back onto the job.

Runs once, after the ``render_scene`` fan-out has fully converged -- the same "join after a
fan-out" position ``assign_tiers`` occupies between the first two fan-outs, except this join's
work (concat) genuinely needs every segment's finished clip rather than being structurally
required the way ``collect_scenes`` is.
"""

from langgraph.runtime import Runtime

from core.graph.context import GraphContext
from core.graph.nodes.render_scene import local_clip_path
from core.graph.state import GraphState
from core.models import JobStatus
from mux.concat_segments import concat_segments

# {job_id}/final.mp4 -- sibling to synthesize.py's SEGMENT_AUDIO_KEY and render_scene.py's
# SEGMENT_CLIP_KEY; this is the node that produces the final video, so it owns this key.
FINAL_VIDEO_KEY = "{job_id}/final.mp4"


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
    await concat_segments(clips, dest, durations_ms=durations_ms)

    key = FINAL_VIDEO_KEY.format(job_id=job.job_id)
    await context.storage.put_file(key, dest, content_type="video/mp4")

    updated_job = job.model_copy(
        update={"segments": ordered, "status": JobStatus.SUCCEEDED, "video_key": key}
    )
    return {"job": updated_job}
