"""Tier 1 -- several screenshots of different reveal states, crossfaded into a clip.

Per the scene-templates skill, 3-5 states is the documented range; 4 is chosen here (evenly
spaced across the whole timeline) so every template's entrance choreography -- which must fully
resolve by roughly 35% of the duration, see the T17 plan -- has settled well before the later
capture points land in the "breathe" phase.
"""

from pathlib import Path

from interfaces import RenderBackend
from mux.frames_to_clip import crossfade

REVEAL_STATE_COUNT = 4


async def render_reveal(
    render: RenderBackend, composition: Path, dest: Path, *, duration_ms: int, fps: int
) -> Path:
    """Capture ``composition`` at ``REVEAL_STATE_COUNT`` evenly-spaced timestamps and crossfade
    them, in order, into ``dest``. Returns ``dest``."""
    duration_s = duration_ms / 1000
    at_seconds = [duration_s * i / (REVEAL_STATE_COUNT - 1) for i in range(REVEAL_STATE_COUNT)]
    stills = await render.capture(composition, dest.parent, at_seconds=at_seconds)
    return await crossfade(stills, dest, duration_ms=duration_ms, fps=fps)
