"""Video and subtitle artifacts, served through ``Storage`` (T21) -- never a raw filesystem path,
so this route works unchanged under either ``RUNTIME_ENV``.

``Storage.url()``'s own docstring says its return value is "opaque to core/ -- only the API layer
dereferences it." Sniffing the scheme is that dereferencing: an ``http(s)://`` URL (Blob's SAS
URL) is browser-fetchable, so that branch redirects; anything else (``DiskStorage``'s
``file://``, ``FakeStorage``'s ``memory://``) is not, so that branch streams the bytes itself.
Neither branch names a concrete adapter class -- config.py stays the only module allowed to.
"""

import mimetypes

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, Response

from core.models import VideoJob
from interfaces import ObjectNotFound, Storage

router = APIRouter()


async def _serve(storage: Storage, key: str) -> Response:
    try:
        url = await storage.url(key)
    except ObjectNotFound:
        raise HTTPException(404, f"no artifact at {key!r}") from None
    if url.startswith(("http://", "https://")):
        return RedirectResponse(url)
    # Anything else -- DiskStorage's file://, FakeStorage's memory:// -- is a scheme no browser
    # can fetch directly, so this process resolves it itself rather than trying to enumerate
    # every non-web scheme an implementation might opaquely return.
    data = await storage.get_bytes(key)
    content_type = mimetypes.guess_type(key)[0] or "application/octet-stream"
    return Response(content=data, media_type=content_type)


@router.get("/jobs/{job_id}/video")
async def get_video(job_id: str, request: Request) -> Response:
    job = await _job_or_404(request, job_id)
    if job.video_key is None:
        raise HTTPException(404, f"job {job_id!r} has no finished video yet")
    return await _serve(request.app.state.adapters.storage, job.video_key)


@router.get("/jobs/{job_id}/subtitles")
async def get_subtitles(job_id: str, request: Request) -> Response:
    job = await _job_or_404(request, job_id)
    if job.subtitles_key is None:
        raise HTTPException(404, f"job {job_id!r} has no subtitles")
    return await _serve(request.app.state.adapters.storage, job.subtitles_key)


async def _job_or_404(request: Request, job_id: str) -> VideoJob:
    try:
        return await request.app.state.job_store.load(job_id)
    except ObjectNotFound:
        raise HTTPException(404, f"no job {job_id!r}") from None
