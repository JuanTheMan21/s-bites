"""Real-toolchain verification for T18H's ``hfDropIfPastCaptionBand`` (``_annotations.html``),
wired into ``_block_code_panel.html`` and ``_block_code_diff.html``.

Confirmed live, not hypothetical: a real render (``t18h-showcase-binary-search`` segment 7, "how
binary search works") composed a 10-line ``CODE_PANEL`` with a genuinely long caption -- neither
alone excessive, but combined they pushed the caption paragraph's own bottom edge exactly onto the
caption band's own top edge (0.8574, ``_captions.html``'s documented fraction), colliding with a
subtitle word. ``CODE_PANEL``/``CODE_DIFF`` have no per-item height to shrink the way
``SEQUENCE_DIAGRAM``/``ARRAY_GRID`` do (T18G's F7) -- a single caption paragraph's height depends
on word-wrap, not a controllable row count -- so the fix drops the caption instead of animating it
in when it would land past the band, the same "colliding is worse than missing" call this
project's annotation-dropping logic already makes.
"""

import json
import shutil
import subprocess

import pytest

from core.block_types import BlockType
from core.models import Tier
from core.scene_schemas import ComposedBlock, ComposedScene
from rendering.render_segment import render_segment
from tests.segment_examples import a_segment

pytestmark = pytest.mark.local_live

_NPX = shutil.which("npx")
DURATION_MS = 21_000
FPS = 24

# The exact content from the real render that found this bug: 10 code lines plus a caption long
# enough to wrap -- neither alone excessive, but combined they overflowed.
_OVERFLOWING_CODE_PANEL: dict = {
    "headline": "Binary search narrows the range",
    "language": "python",
    "caption": (
        "low and high mark the surviving range, and mid splits it so the comparison can "
        "discard one half"
    ),
    "lines": [
        "low = 0",
        "high = len(nums) - 1",
        "while low <= high:",
        "    mid = (low + high) // 2",
        "    if nums[mid] == target:",
        "        break",
        "    elif nums[mid] < target:",
        "        low = mid + 1",
        "    else:",
        "        high = mid - 1",
    ],
    "highlight_lines": [3],
}


def _a_code_panel_segment(payload: dict):
    scene = ComposedScene(
        motif="terminal",
        layout="single",
        blocks=[
            ComposedBlock(
                block_type=BlockType.CODE_PANEL, role="role", anchor_phrase=None, payload=payload
            )
        ],
        continues_previous=False,
    )
    return a_segment(0, duration_ms=DURATION_MS).model_copy(
        update={"tier": Tier.ANIMATED, "scene": scene.model_dump()}
    )


def _run_check(composition_dir) -> dict:
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


async def test_an_overflowing_code_panel_caption_is_dropped_not_left_colliding(
    backend, tmp_path
) -> None:
    """The regression pin for the confirmed real-render bug: a code panel long enough (combined
    with a long caption) to reach the caption band renders clean -- the caption is dropped, not
    left colliding with a subtitle word."""
    segment = _a_code_panel_segment(_OVERFLOWING_CODE_PANEL)
    composition_dir = tmp_path / "comp"
    dest = tmp_path / "clip.mp4"

    result = await render_segment(
        segment, backend, composition_dir=composition_dir, dest=dest, fps=FPS
    )

    assert result == dest
    assert dest.exists() and dest.stat().st_size > 0

    check = _run_check(composition_dir)
    assert check.get("ok") is True, check
    assert check["layout"]["errorCount"] == 0, check["layout"]["findings"]
    assert check["contrast"]["errorCount"] == 0, check["contrast"]["findings"]
