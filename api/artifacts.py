"""Video and subtitle artifacts, served through ``Storage`` (T21) -- never a raw filesystem path,
so this route works unchanged under either ``RUNTIME_ENV``. The actual dereferencing (including
Range/206 support, T24), the SAS lifetimes, and the owner-scoped ``VideoJob`` lookup all live in
``api/artifact_response.py``, where ``api/segments.py`` (T27) reuses them for per-segment
artifacts.
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from api.artifact_response import (
    DOWNLOAD_SAS_TTL_S,
    STREAMED_SAS_TTL_S,
    job_or_404,
    serve_artifact,
)
from api.auth import CurrentPrincipal

router = APIRouter()


@router.get("/jobs/{job_id}/video")
async def get_video(job_id: str, request: Request, principal: CurrentPrincipal) -> Response:
    job = await job_or_404(request, job_id, principal.owner_id)
    if job.video_key is None:
        raise HTTPException(404, f"job {job_id!r} has no finished video yet")
    # Streamed, not downloaded: the window has to outlive someone actually watching and scrubbing.
    return await serve_artifact(
        request,
        request.app.state.adapters.storage,
        job.video_key,
        expires_s=STREAMED_SAS_TTL_S,
    )


@router.get("/jobs/{job_id}/subtitles")
async def get_subtitles(job_id: str, request: Request, principal: CurrentPrincipal) -> Response:
    job = await job_or_404(request, job_id, principal.owner_id)
    if job.subtitles_key is None:
        raise HTTPException(404, f"job {job_id!r} has no subtitles")
    return await serve_artifact(
        request,
        request.app.state.adapters.storage,
        job.subtitles_key,
        expires_s=DOWNLOAD_SAS_TTL_S,
    )
