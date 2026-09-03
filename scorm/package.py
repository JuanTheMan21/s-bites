"""Assembles a SCORM 1.2 package: ``imsmanifest.xml``, a launch page that reports completion
through the SCORM API, the video, and its subtitles when present -- one in-memory zip, never
written to disk, mirroring ``mux/``'s own bytes-in/bytes-out shape.
"""

import zipfile
from html import escape
from io import BytesIO

from scorm.manifest import build_manifest

LAUNCH_FILE = "launch.html"
VIDEO_FILE = "video.mp4"
SUBTITLES_FILE = "subtitles.srt"


def _launch_html(*, title: str, has_subtitles: bool) -> str:
    # `title` is job.topic, user-submitted free text -- escaped the same way manifest.py already
    # escapes it into imsmanifest.xml. Missed here on first pass (project-reviewer, T24-T28
    # checkpoint): unescaped, a topic like "</title><script>...</script>" executes the moment
    # anyone opens launch.html in a browser or an LMS imports and launches the SCO.
    safe_title = escape(title)
    # SCORM 1.2's API discovery algorithm: walk up through parent/opener frames (an LMS embeds
    # the SCO in an iframe, or launches it in a child window) looking for a window exposing
    # `API`, depth-limited to 7 per the spec's own convention.
    track = f'<track kind="subtitles" src="{SUBTITLES_FILE}" default>' if has_subtitles else ""
    return f"""<!doctype html>
<html>
<head><meta charset="utf-8"><title>{safe_title}</title>
<style>html,body{{margin:0;background:#000;height:100%}}video{{width:100%;height:100%}}</style>
</head>
<body>
<video id="v" autoplay controls>
  <source src="{VIDEO_FILE}" type="video/mp4">
  {track}
</video>
<script>
function findAPI(win, tries) {{
  tries = tries || 0;
  if (win.API) return win.API;
  if (tries > 7 || win.parent === win) return null;
  return findAPI(win.parent, tries + 1);
}}
var api = findAPI(window, 0) || (window.opener && findAPI(window.opener, 0));
if (api) {{
  api.LMSInitialize("");
  window.addEventListener("beforeunload", function () {{ api.LMSFinish(""); }});
}}
document.getElementById("v").addEventListener("ended", function () {{
  if (api) {{
    api.LMSSetValue("cmi.core.lesson_status", "completed");
    api.LMSCommit("");
  }}
}});
</script>
</body>
</html>
"""


def build_scorm_package(*, job_id: str, title: str, video: bytes, subtitles: bytes | None) -> bytes:
    """The complete zip a browser can download directly and an LMS can import unmodified."""
    has_subtitles = subtitles is not None
    resource_files = [VIDEO_FILE, *([SUBTITLES_FILE] if has_subtitles else [])]
    manifest = build_manifest(
        job_id=job_id, title=title, launch_file=LAUNCH_FILE, resource_files=resource_files
    )
    launch_html = _launch_html(title=title, has_subtitles=has_subtitles)

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("imsmanifest.xml", manifest)
        zf.writestr(LAUNCH_FILE, launch_html)
        zf.writestr(VIDEO_FILE, video)
        if has_subtitles:
            zf.writestr(SUBTITLES_FILE, subtitles)
    return buffer.getvalue()
