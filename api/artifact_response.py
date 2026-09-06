"""Shared plumbing between ``api/artifacts.py``, ``api/segments.py`` and ``api/scorm.py`` (T27):
dereferencing a ``Storage`` key into an HTTP response, and loading the ``VideoJob`` a request's
``job_id`` names -- for the caller who owns it, and nobody else (T38A).

``job_or_404`` is the single ownership chokepoint for six of the eleven job-scoped routes, which
is why they all go through it rather than each loading a job themselves.
"""

import mimetypes

from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse, Response

from api.byte_range import ranged_response
from core.video_job import VideoJob
from interfaces import ObjectNotFound, Storage

# T38A. The task text asked for "minutes", which taken literally breaks playback: a browser
# <video> re-requests byte ranges as the viewer scrubs, so a SAS that dies after five minutes
# kills a video part-way through watching it -- and adapters/azure/storage.py back-dates the
# start by a five-minute CLOCK_SKEW, eating most of a short window before it begins. So: long
# enough to watch something, short enough to matter, and split by how the artifact is consumed.
STREAMED_SAS_TTL_S = 900
DOWNLOAD_SAS_TTL_S = 300


async def serve_artifact(
    request: Request, storage: Storage, key: str, *, expires_s: int = DOWNLOAD_SAS_TTL_S
) -> Response:
    """``Storage.url()``'s own docstring says its return value is "opaque to core/ -- only the
    API layer dereferences it." Sniffing the scheme is that dereferencing: an ``http(s)://`` URL
    (Blob's SAS URL) is browser-fetchable and already supports Range natively, so that branch
    just redirects. Anything else (``DiskStorage``'s ``file://``, ``FakeStorage``'s
    ``memory://``) is not, so this process resolves it itself -- and since it already has the
    full bytes in hand at that point, also answers whatever Range request came in.

    The caller's ownership is checked before this is ever reached, so a SAS URL is only minted
    for the owner. It remains an unauthenticated bearer capability for ``expires_s`` afterwards,
    though: anyone the URL is forwarded to can fetch it until it expires. That is the reason the
    window is no longer the interface's hour-long default.
    """
    try:
        url = await storage.url(key, expires_s=expires_s)
    except ObjectNotFound:
        raise HTTPException(404, f"no artifact at {key!r}") from None
    if url.startswith(("http://", "https://")):
        return RedirectResponse(url)
    data = await storage.get_bytes(key)
    content_type = mimetypes.guess_type(key)[0] or "application/octet-stream"
    return ranged_response(data, content_type, request.headers.get("range"))


async def job_or_404(request: Request, job_id: str, owner_id: str) -> VideoJob:
    """The job, if this caller owns it. A job owned by someone else is not found rather than
    forbidden -- see ``api/job_store.py``: the owner is part of the key, so there is no branch
    here that could tell the two apart even if it wanted to.
    """
    try:
        return await request.app.state.job_store.load(owner_id, job_id)
    except ObjectNotFound:
        raise HTTPException(404, f"no job {job_id!r}") from None
