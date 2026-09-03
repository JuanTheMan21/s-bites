"""Shared plumbing between ``api/artifacts.py`` and ``api/segments.py`` (T27): dereferencing a
``Storage`` key into an HTTP response, and loading the ``VideoJob`` a request's ``job_id`` names.

Split out rather than left in ``api/artifacts.py`` so both routers can share it without either
importing the other's internals, and so ``api/artifacts.py`` stays under the 200-line ceiling once
Range support (``api/byte_range.py``) lands on the byte-streaming branch below.
"""

import mimetypes

from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse, Response

from api.byte_range import ranged_response
from core.models import VideoJob
from interfaces import ObjectNotFound, Storage


async def serve_artifact(request: Request, storage: Storage, key: str) -> Response:
    """``Storage.url()``'s own docstring says its return value is "opaque to core/ -- only the
    API layer dereferences it." Sniffing the scheme is that dereferencing: an ``http(s)://`` URL
    (Blob's SAS URL) is browser-fetchable and already supports Range natively, so that branch
    just redirects. Anything else (``DiskStorage``'s ``file://``, ``FakeStorage``'s
    ``memory://``) is not, so this process resolves it itself -- and since it already has the
    full bytes in hand at that point, also answers whatever Range request came in.
    """
    try:
        url = await storage.url(key)
    except ObjectNotFound:
        raise HTTPException(404, f"no artifact at {key!r}") from None
    if url.startswith(("http://", "https://")):
        return RedirectResponse(url)
    data = await storage.get_bytes(key)
    content_type = mimetypes.guess_type(key)[0] or "application/octet-stream"
    return ranged_response(data, content_type, request.headers.get("range"))


async def job_or_404(request: Request, job_id: str) -> VideoJob:
    try:
        return await request.app.state.job_store.load(job_id)
    except ObjectNotFound:
        raise HTTPException(404, f"no job {job_id!r}") from None
