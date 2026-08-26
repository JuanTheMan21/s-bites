"""The one place an ffmpeg subprocess is actually spawned. Every ``mux/`` module that shells out
to ffmpeg -- ``frames_to_clip.py``, ``audio_mux.py``, ``concat_segments.py`` -- calls
``run_ffmpeg`` rather than repeating the spawn/timeout/kill dance three times.

Extracted from ``frames_to_clip.py`` at T18, once a second and third call site needed the exact
same behaviour: spawn, wait with a timeout, kill the process on timeout (not just cancel the
``communicate()`` future -- that leaves ffmpeg itself running), and raise ``RenderFailed`` for a
nonzero exit or for an exit-0-but-nothing-written result.
"""

import asyncio
import contextlib
from pathlib import Path

from interfaces import RenderFailed

DEFAULT_TIMEOUT_S = 60.0


async def run_ffmpeg(
    args: list[str], *, context: str, timeout_s: float = DEFAULT_TIMEOUT_S
) -> None:
    """Run ``ffmpeg`` with ``args``, whose last element must be the destination path.

    Raises:
        RenderFailed: ffmpeg could not start, timed out, exited nonzero, or exited 0 without
            writing a non-empty file to the destination.
    """
    dest = Path(args[-1])
    dest.parent.mkdir(parents=True, exist_ok=True)

    try:
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg",
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except OSError as exc:
        raise RenderFailed(f"{context}: could not start ffmpeg: {exc}") from exc

    try:
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout_s)
    except TimeoutError as exc:
        proc.kill()
        with contextlib.suppress(Exception):
            await proc.wait()
        raise RenderFailed(f"{context}: ffmpeg timed out after {timeout_s}s") from exc

    if proc.returncode != 0:
        raise RenderFailed(
            f"{context}: ffmpeg exited {proc.returncode}: {stderr.decode(errors='replace')[-2000:]}"
        )
    if not dest.exists() or dest.stat().st_size == 0:
        raise RenderFailed(f"{context}: ffmpeg exited 0 but wrote no video to {dest}")
