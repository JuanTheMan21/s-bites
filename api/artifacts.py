"""Video and subtitle artifacts, served through ``Storage`` (T21) -- never a raw filesystem path,
so this route works unchanged under either ``RUNTIME_ENV``. The actual dereferencing (including
Range/206 support, T24) and the shared ``VideoJob`` lookup live in ``api/artifact_response.py``,
where ``api/segments.py`` (T27) reuses both for per-segment artifacts.
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from api.artifact_response import job_or_404, serve_artifact

router = APIRouter()


@router.get("/jobs/{job_id}/video")
async def get_video(job_id: str, request: Request) -> Response:
    job = await job_or_404(request, job_id)
    if job.video_key is None:
        raise HTTPException(404, f"job {job_id!r} has no finished video yet")
    return await serve_artifact(request, request.app.state.adapters.storage, job.video_key)


@router.get("/jobs/{job_id}/subtitles")
async def get_subtitles(job_id: str, request: Request) -> Response:
    job = await job_or_404(request, job_id)
    if job.subtitles_key is None:
        raise HTTPException(404, f"job {job_id!r} has no subtitles")
    return await serve_artifact(request, request.app.state.adapters.storage, job.subtitles_key)
