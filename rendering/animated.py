"""Tier 2 -- the full HyperFrames frame-by-frame render.

No ffmpeg step here, unlike Tier 0/1: the HyperFrames CLI already produces the final MP4 from the
composition's own ``data-duration`` (itself the Jinja-injected measured ``duration_ms``, per
Invariant 1), so this module is a thin, single-purpose wrapper over ``RenderBackend.render``.
"""

from pathlib import Path

from interfaces import RenderBackend


async def render_animated(
    render: RenderBackend, composition: Path, dest: Path, *, duration_ms: int, fps: int
) -> Path:
    """Render ``composition`` frame by frame to ``dest``. Returns ``dest``."""
    return await render.render(composition, dest, fps=fps, duration_ms=duration_ms)
