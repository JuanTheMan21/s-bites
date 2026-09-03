"""``GET /jobs/{id}/scorm`` (T36): the finished video packaged as a SCORM 1.2 course an LMS can
import directly -- manifest, a launch page reporting completion through the SCORM API, the
video, and subtitles when present. Read through ``Storage`` the same way ``api/artifacts.py``
serves the raw video, never a filesystem path.
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from api.artifact_response import job_or_404
from interfaces import ObjectNotFound
from scorm.package import build_scorm_package

router = APIRouter()


@router.get("/jobs/{job_id}/scorm")
async def get_scorm_package(job_id: str, request: Request) -> Response:
    job = await job_or_404(request, job_id)
    if job.video_key is None:
        raise HTTPException(404, f"job {job_id!r} has no finished video yet")

    storage = request.app.state.adapters.storage
    video = await storage.get_bytes(job.video_key)
    subtitles: bytes | None = None
    if job.subtitles_key is not None:
        try:
            subtitles = await storage.get_bytes(job.subtitles_key)
        except ObjectNotFound:
            # The docstring on VideoJob.subtitles_key already allows it to point at nothing
            # meaningful; a package with just the video is still a valid, importable SCO.
            subtitles = None

    package = build_scorm_package(job_id=job_id, title=job.topic, video=video, subtitles=subtitles)
    return Response(
        content=package,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{job_id}.zip"'},
    )
