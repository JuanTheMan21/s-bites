"""T36: SCORM 1.2 manifest and package assembly, against plain bytes -- no FastAPI, no Storage."""

import zipfile
from io import BytesIO

from scorm.manifest import build_manifest
from scorm.package import LAUNCH_FILE, SUBTITLES_FILE, VIDEO_FILE, build_scorm_package


def test_manifest_names_the_launch_file_and_every_resource() -> None:
    xml = build_manifest(
        job_id="abc123",
        title="Teach me about SQL injection",
        launch_file="launch.html",
        resource_files=["video.mp4", "subtitles.srt"],
    )
    assert 'href="launch.html"' in xml
    assert 'href="video.mp4"' in xml
    assert 'href="subtitles.srt"' in xml
    assert "Teach me about SQL injection" in xml
    assert "s-bites-abc123" in xml


def test_manifest_escapes_a_title_with_xml_special_characters() -> None:
    xml = build_manifest(
        job_id="x",
        title='<script>alert("hi")</script> & friends',
        launch_file="launch.html",
        resource_files=["video.mp4"],
    )
    assert "<script>" not in xml
    assert "&lt;script&gt;" in xml
    assert "&amp; friends" in xml


def test_launch_page_escapes_a_title_with_html_special_characters() -> None:
    """Regression (project-reviewer, T24-T28 checkpoint): title is job.topic, user-submitted free
    text -- manifest.py escaped it into imsmanifest.xml from the start, but the launch page's own
    <title> interpolated it raw. An unescaped "</title><script>...</script>" topic would execute
    the moment anyone opened launch.html or an LMS launched the imported SCO."""
    package = build_scorm_package(
        job_id="x", title="</title><script>alert(1)</script>", video=b"v", subtitles=None
    )
    with zipfile.ZipFile(BytesIO(package)) as zf:
        launch_html = zf.read(LAUNCH_FILE).decode()
    assert "<script>alert(1)</script>" not in launch_html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in launch_html


def test_package_without_subtitles_omits_the_subtitles_entry() -> None:
    package = build_scorm_package(job_id="j1", title="x", video=b"fake-mp4-bytes", subtitles=None)
    with zipfile.ZipFile(BytesIO(package)) as zf:
        names = set(zf.namelist())
        assert names == {"imsmanifest.xml", LAUNCH_FILE, VIDEO_FILE}
        assert zf.read(VIDEO_FILE) == b"fake-mp4-bytes"
        manifest = zf.read("imsmanifest.xml").decode()
        assert SUBTITLES_FILE not in manifest


def test_package_with_subtitles_includes_all_four_files() -> None:
    package = build_scorm_package(
        job_id="j2",
        title="x",
        video=b"video-bytes",
        subtitles=b"1\n00:00:00,000 --> 00:00:01,000\nHi\n",
    )
    with zipfile.ZipFile(BytesIO(package)) as zf:
        names = set(zf.namelist())
        assert names == {"imsmanifest.xml", LAUNCH_FILE, VIDEO_FILE, SUBTITLES_FILE}
        assert zf.read(SUBTITLES_FILE).startswith(b"1\n00:00:00,000")
        launch_html = zf.read(LAUNCH_FILE).decode()
        assert SUBTITLES_FILE in launch_html


def test_launch_page_carries_the_scorm_api_discovery_and_completion_calls() -> None:
    package = build_scorm_package(job_id="j3", title="x", video=b"v", subtitles=None)
    with zipfile.ZipFile(BytesIO(package)) as zf:
        launch_html = zf.read(LAUNCH_FILE).decode()
    assert "LMSInitialize" in launch_html
    assert "LMSSetValue" in launch_html
    assert "cmi.core.lesson_status" in launch_html
    assert "completed" in launch_html
    assert "LMSFinish" in launch_html
