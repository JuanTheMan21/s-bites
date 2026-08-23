"""The two ``RenderBackend`` implementations, held to one set of shape assertions.

``FakeRenderBackend`` writes placeholder bytes rather than a real MP4 (there is no offline ffmpeg
fake), so this cannot assert byte-identical output -- only the contract's *shape*: return types,
ordering, and that ``lint`` never raises. That much runs for both implementations, always.

The real ``PlaywrightHyperFramesRenderBackend`` needs a real browser and the HyperFrames CLI
installed, so it is marked ``local_live`` (D56's bargain, for a local dependency instead of an
Azure one) both as the fixture's third param and again on the dedicated behavioral tests below,
which check what only a real render can prove: that a good composition lints clean and a broken
one does not, and that a render actually produces playable video.
"""

from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from adapters.local import hyperframes_cli
from adapters.local.render_backend import PlaywrightHyperFramesRenderBackend
from interfaces import RenderBackend, RenderFailed
from tests.fakes import FakeRenderBackend

IMPLEMENTATIONS = ["fake", pytest.param("local", marks=pytest.mark.local_live)]

FIXTURES = Path(__file__).parent / "fixtures" / "render_backend"
GOOD_COMPOSITION = FIXTURES / "index.html"
BROKEN_COMPOSITION = FIXTURES / "broken" / "index.html"


@pytest.fixture(params=IMPLEMENTATIONS)
async def backend(request: pytest.FixtureRequest) -> AsyncIterator[RenderBackend]:
    if request.param == "fake":
        yield FakeRenderBackend()
        return

    real = PlaywrightHyperFramesRenderBackend(max_attempts=1, timeout_s=90.0)
    try:
        yield real
    finally:
        await real.aclose()


async def test_capture_returns_one_path_per_position_in_the_order_requested(
    backend: RenderBackend, tmp_path: Path
) -> None:
    paths = await backend.capture(GOOD_COMPOSITION, tmp_path, at_seconds=[0.0, 1.0, 2.5])

    assert len(paths) == 3
    for path in paths:
        assert path.exists()
        assert path.parent == tmp_path


async def test_render_returns_the_destination_and_writes_something_there(
    backend: RenderBackend, tmp_path: Path
) -> None:
    dest = tmp_path / "clip.mp4"

    result = await backend.render(GOOD_COMPOSITION, dest, fps=24, duration_ms=3000)

    assert result == dest
    assert dest.exists()
    assert dest.stat().st_size > 0


async def test_lint_never_raises_and_returns_a_list(backend: RenderBackend) -> None:
    findings = await backend.lint(GOOD_COMPOSITION)
    assert isinstance(findings, list)


@pytest.mark.local_live
async def test_a_known_good_composition_lints_clean() -> None:
    backend = PlaywrightHyperFramesRenderBackend()
    try:
        assert await backend.lint(GOOD_COMPOSITION) == []
    finally:
        await backend.aclose()


@pytest.mark.local_live
async def test_a_composition_missing_timeline_registration_reports_findings() -> None:
    backend = PlaywrightHyperFramesRenderBackend()
    try:
        findings = await backend.lint(BROKEN_COMPOSITION)
        assert findings != []
    finally:
        await backend.aclose()


@pytest.mark.local_live
async def test_a_real_render_produces_a_valid_playable_clip(tmp_path: Path) -> None:
    """The one assertion the fake structurally cannot make (see the module docstring)."""
    import subprocess

    backend = PlaywrightHyperFramesRenderBackend(quality="draft")
    dest = tmp_path / "clip.mp4"
    try:
        await backend.render(GOOD_COMPOSITION, dest, fps=24, duration_ms=3000)
    finally:
        await backend.aclose()

    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_format", str(dest)],
        capture_output=True,
        text=True,
    )
    assert probe.returncode == 0, probe.stderr
    assert "format_name=mov,mp4" in probe.stdout or "mp4" in probe.stdout


@pytest.mark.local_live
async def test_a_timeout_raises_render_failed_and_leaves_the_backend_usable(
    tmp_path: Path,
) -> None:
    """Regression: an earlier version left the timed-out hyperframes process (and its node/
    chrome-headless-shell children) running, orphaned, with nothing to stop a retry from racing
    a second writer against the same destination. A real render takes several seconds, so a
    near-zero timeout reliably trips the timeout path rather than the tool's own error path."""
    with pytest.raises(RenderFailed):
        await hyperframes_cli.render(
            GOOD_COMPOSITION,
            tmp_path / "too-fast.mp4",
            fps=24,
            quality="draft",
            timeout_s=0.01,
        )

    # The backend must still work afterward -- proof the timeout path cleaned up rather than
    # leaving state (a lock, an orphaned process holding the output path) behind. A generous
    # timeout here: this call exists to prove recovery, not to pin render speed under whatever
    # else the full suite has running concurrently.
    dest = tmp_path / "clip.mp4"
    result = await hyperframes_cli.render(
        GOOD_COMPOSITION, dest, fps=24, quality="draft", timeout_s=90.0
    )
    assert result == dest
    assert dest.stat().st_size > 0
