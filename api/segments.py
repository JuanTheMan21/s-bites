"""Per-segment artifacts (T27): narration audio, the composed scene, and the rendered clip,
fetched by ``job_id`` + segment index rather than a bespoke endpoint per artifact kind.

No model change needed for audio: ``SEGMENT_AUDIO_KEY`` is imported directly from the node that
writes it (``core/graph/nodes/synthesize.py``), the same way ``clip_key`` is read straight off
``Segment`` -- one definition each, so this router can never drift from where those nodes
actually persist. Scene HTML itself is never persisted through ``Storage`` (it exists only in the
run's ``working_dir``); ``Segment.scene``, the authoring source of truth, is served instead.
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, Response

from api.artifact_response import job_or_404, serve_artifact
from core.graph.nodes.synthesize import SEGMENT_AUDIO_KEY
from core.models import Segment
from core.video_job import VideoJob

router = APIRouter()


def _segment_or_404(job: VideoJob, index: int) -> Segment:
    for segment in job.segments:
        if segment.index == index:
            return segment
    raise HTTPException(404, f"job {job.job_id!r} has no segment {index}")


@router.get("/jobs/{job_id}/segments/{index}/audio")
async def get_segment_audio(job_id: str, index: int, request: Request) -> Response:
    job = await job_or_404(request, job_id)
    segment = _segment_or_404(job, index)
    # duration_ms is set at the same stage as the audio write (core/models.py's own docstring),
    # so it doubles as the "has narration audio" guard without a new field.
    if segment.duration_ms is None:
        raise HTTPException(404, f"segment {index} has no narration audio yet")
    key = SEGMENT_AUDIO_KEY.format(job_id=job_id, index=index)
    return await serve_artifact(request, request.app.state.adapters.storage, key)


@router.get("/jobs/{job_id}/segments/{index}/clip")
async def get_segment_clip(job_id: str, index: int, request: Request) -> Response:
    job = await job_or_404(request, job_id)
    segment = _segment_or_404(job, index)
    if segment.clip_key is None:
        raise HTTPException(404, f"segment {index} has no rendered clip yet")
    return await serve_artifact(request, request.app.state.adapters.storage, segment.clip_key)


@router.get("/jobs/{job_id}/segments/{index}/scene")
async def get_segment_scene(job_id: str, index: int, request: Request) -> Response:
    job = await job_or_404(request, job_id)
    segment = _segment_or_404(job, index)
    if segment.scene is None:
        raise HTTPException(404, f"segment {index} has no composed scene yet")
    return JSONResponse(segment.scene)
