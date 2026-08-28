"""Every real block, at every tier, through the real backend and the real CLI's ``check``.

``local_live``, following ``test_render_backend_parity.py``'s shape: real
``PlaywrightHyperFramesRenderBackend``, ``aclose()`` in ``finally``. This is the "render every
block at all three tiers explicitly" sweep ``handoff.md`` asks for -- a real job leaves Tier 0
unexercised entirely (D79), so nothing else in this suite renders it against a real browser.

T18B: parametrized by ``BlockType`` (each rendered alone, ``SINGLE`` layout) rather than
``VisualIntent`` -- the dispatch this sweep exercises moved from intent-to-template to
layout-plus-blocks.

``check`` (not just the interface's own ``lint``) additionally runs here as a second, stricter
gate: WCAG contrast, the frozen-sweep guard, and the rest of the layout audit all found real bugs
in these templates during authoring (an unsized root, ambient motion invisible below the checker's
own 0.2 opacity floor, an SVG stroke-draw that never moves its own bounding box, and two genuine
contrast failures) that ``lint`` alone does not catch. Per the T17 plan, ``render_segment`` itself
only ever gates on ``RenderBackend.lint`` -- ``check`` is not part of the interface contract and is
slower and more opinionated than what should block an ordinary job, so this extra scrutiny lives
here, in template authoring's own verification, rather than in the render path itself.
"""

import json
import shutil
import subprocess

import pytest

from core.block_types import BlockType
from core.models import Tier
from rendering.render_segment import render_segment
from tests.segment_examples import an_authored_segment

pytestmark = pytest.mark.local_live

_NPX = shutil.which("npx")

# Short, deliberately -- this sweep is 6 block types x 3 Tiers, and Tier 2's render time scales
# with duration (D16). A realistic ~21s segment would make the matrix take tens of minutes for
# no added coverage: contrast/layout/lint findings are structural properties of the block, not a
# function of how long the clip runs, and the duration-match assertion is exactly as meaningful
# at 4s as at 21s.
DURATION_MS = 4_000
FPS = 24


def _run_check(composition_dir) -> dict:
    # _NPX, not the bare string "npx": on Windows, npx is npx.cmd, and CreateProcess (which
    # subprocess.run uses without shell=True) does not resolve PATHEXT itself -- the same reason
    # adapters/local/hyperframes_cli.py resolves it this way rather than passing "npx" directly.
    assert _NPX is not None, "npx is not on PATH"
    result = subprocess.run(
        [_NPX, "--no-install", "hyperframes", "check", "--json", str(composition_dir)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    return json.loads(result.stdout)


@pytest.fixture
async def backend():
    from adapters.local.render_backend import PlaywrightHyperFramesRenderBackend

    real = PlaywrightHyperFramesRenderBackend(quality="draft", max_attempts=1, timeout_s=90.0)
    try:
        yield real
    finally:
        await real.aclose()


@pytest.mark.parametrize("block_type", list(BlockType))
@pytest.mark.parametrize("tier", list(Tier))
async def test_every_block_renders_a_valid_clip_at_every_tier(
    backend, tmp_path, block_type: BlockType, tier: Tier
) -> None:
    segment = an_authored_segment(0, block_type, tier, duration_ms=DURATION_MS)
    composition_dir = tmp_path / "comp"
    dest = tmp_path / "clip.mp4"

    result = await render_segment(
        segment, backend, composition_dir=composition_dir, dest=dest, fps=FPS
    )

    assert result == dest
    assert dest.exists() and dest.stat().st_size > 0

    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=nw=1:nk=1",
            str(dest),
        ],
        capture_output=True,
        text=True,
    )
    assert probe.returncode == 0, probe.stderr
    measured_ms = round(float(probe.stdout.strip()) * 1000)
    assert measured_ms == pytest.approx(DURATION_MS, abs=100)

    check = _run_check(composition_dir)
    assert check.get("ok") is True, check
    assert check["contrast"]["errorCount"] == 0, check["contrast"]["findings"]
    assert check["layout"]["errorCount"] == 0, check["layout"]["findings"]
