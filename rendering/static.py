"""Tier 0 -- one screenshot, held for the whole measured audio duration.

Tier 0's single frame is deliberately the composition's fully-revealed **end** state, not its
opening frame. Per D79, Tier 0 is a rendering floor -- the form every segment can fall back to,
not a teaser -- so it should show the complete picture, not a half-built one.
"""

from pathlib import Path

from interfaces import RenderBackend
from mux.frames_to_clip import hold_frame


async def render_static(
    render: RenderBackend, composition: Path, dest: Path, *, duration_ms: int, fps: int
) -> Path:
    """Capture ``composition`` at its end state and hold it for ``duration_ms``. Returns ``dest``."""
    [still] = await render.capture(composition, dest.parent, at_seconds=[duration_ms / 1000])
    return await hold_frame(still, dest, duration_ms=duration_ms, fps=fps)
