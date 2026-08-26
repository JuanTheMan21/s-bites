"""Tier 1 -- several screenshots of different reveal states, crossfaded into a clip.

Per the scene-templates skill, 3-5 states is the documented range; 4 is chosen here so every
template's entrance choreography -- which must fully resolve by roughly 35% of the duration, see
the T17 plan -- has settled well before the later capture points land in the "breathe" phase.

**Not evenly spaced from t=0.** Every template's entrance starts from `opacity:0` and only begins
tweening in around t=0.1-0.5s, so a literal t=0 capture is the pre-animation blank frame --
``mux/frames_to_clip.py::crossfade`` then holds that blank frame for roughly an eighth of the
segment's duration before its first transition, which is exactly the several seconds of near-
nothing a real render surfaced. ``SETTLE_S`` pushes the first sample past that blank instant;
capped rather than a flat fraction so a short segment doesn't spend most of its four states
past a settle window sized for a long one.
"""

from pathlib import Path

from interfaces import RenderBackend
from mux.frames_to_clip import crossfade

REVEAL_STATE_COUNT = 4
SETTLE_S_CAP = 1.5
SETTLE_FRACTION = 0.12


async def render_reveal(
    render: RenderBackend, composition: Path, dest: Path, *, duration_ms: int, fps: int
) -> Path:
    """Capture ``composition`` at ``REVEAL_STATE_COUNT`` timestamps -- spread from just past
    entrance to the fully-settled end -- and crossfade them, in order, into ``dest``. Returns
    ``dest``."""
    duration_s = duration_ms / 1000
    settle_s = min(SETTLE_S_CAP, duration_s * SETTLE_FRACTION)
    at_seconds = [
        settle_s + (duration_s - settle_s) * i / (REVEAL_STATE_COUNT - 1)
        for i in range(REVEAL_STATE_COUNT)
    ]
    stills = await render.capture(composition, dest.parent, at_seconds=at_seconds)
    return await crossfade(stills, dest, duration_ms=duration_ms, fps=fps)
