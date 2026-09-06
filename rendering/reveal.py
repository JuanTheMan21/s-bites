"""Tier 1 -- several screenshots of different reveal states, crossfaded into a clip.

T18K/D161: capture instants and transition placement now come from
``rendering/still_plan.py``'s plan (written by ``rendering/compose.py`` beside the composition it
describes) rather than a fixed evenly-spaced schedule -- the old schedule had no idea a caption
cue existed, so a 9-cue segment could only ever show 4 of them and ``xfade`` visibly smeared one
cue's text into the next. Every cue start is now a mandatory sample, and the transition landing on
a cue change is a hard cut (one frame) rather than a real blend, so two different captions are
never shown mixed together mid-fade.

A composition with no sidecar (composed by something other than ``compose_scene``, or a stale
fixture) falls back to the pre-T18K evenly-spaced schedule below, unchanged. **Not evenly spaced
from t=0**: every template's entrance starts from `opacity:0` and only begins tweening in around
t=0.1-0.5s, so a literal t=0 capture is the pre-animation blank frame -- ``settle_seconds`` pushes
the first sample past that blank instant.
"""

from pathlib import Path

from interfaces import RenderBackend
from mux.frames_to_clip import crossfade
from rendering.still_plan import read_still_plan, settle_seconds

# The pre-T18K fallback's state count -- unused by the plan-driven path, kept for a composition
# with no sidecar.
REVEAL_STATE_COUNT = 4


async def render_reveal(
    render: RenderBackend, composition: Path, dest: Path, *, duration_ms: int, fps: int
) -> Path:
    """Capture ``composition`` at its planned still instants -- caption-cue starts plus block
    reveal times, see the module docstring -- and crossfade them, in order, into ``dest``.
    Returns ``dest``."""
    duration_s = duration_ms / 1000
    samples = read_still_plan(composition.parent)

    if samples is None:
        settle_s = settle_seconds(duration_s)
        at_seconds = [
            settle_s + (duration_s - settle_s) * i / (REVEAL_STATE_COUNT - 1)
            for i in range(REVEAL_STATE_COUNT)
        ]
        stills = await render.capture(composition, dest.parent, at_seconds=at_seconds)
        return await crossfade(stills, dest, duration_ms=duration_ms, fps=fps)

    at_seconds = [sample.at_s for sample in samples]
    stills = await render.capture(composition, dest.parent, at_seconds=at_seconds)
    if len(stills) == 1:
        return await crossfade(stills, dest, duration_ms=duration_ms, fps=fps)

    # A transition landing on a cue change is a hard cut (one frame, ffmpeg's own floor on a
    # valid xfade) rather than a real blend -- blending two different captions together is the
    # exact defect this module exists to remove. Every other transition keeps a real, if short,
    # crossfade.
    hard_cut_s = 1 / fps
    xfade_s = [
        hard_cut_s
        if samples[i + 1].is_cue_boundary
        else min(0.35, 0.4 * (at_seconds[i + 1] - at_seconds[i]))
        for i in range(len(samples) - 1)
    ]
    return await crossfade(
        stills, dest, duration_ms=duration_ms, fps=fps, at_seconds=at_seconds, xfade_s=xfade_s
    )
