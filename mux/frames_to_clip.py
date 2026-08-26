"""Turning Tier 0/1 stills into a silent video clip via ffmpeg.

Per CLAUDE.md, ffmpeg subprocess calls live in ``mux/`` -- this module, plus T18's
``audio_mux.py``/``concat_segments.py``, all sharing one spawn/timeout/kill implementation in
``mux/ffmpeg_run.py`` rather than each repeating it.

Both functions pin the output's duration to ``duration_ms`` *exactly* via ``-t`` on the final
encode, the same discipline D18 used for audio mux -- the internal timing math below is built to
land at or past that mark, and ``-t`` is what makes the guarantee exact rather than approximate.
"""

from collections.abc import Sequence
from pathlib import Path

from mux.ffmpeg_run import run_ffmpeg

# libx264 refuses odd width/height ("width not divisible by 2"). Real captures are always the
# composition's own even data-width/data-height, but nothing here should assume that -- an odd
# input dimension would otherwise fail this encode for a reason that has nothing to do with the
# actual composition. `ceil`, not `trunc`: rounding a 1px source *down* to the nearest even number
# is 0, which libx264 also refuses -- found by a test image narrow enough to hit exactly that.
_EVEN_DIMENSIONS_FILTER = "scale=2*ceil(iw/2):2*ceil(ih/2)"


async def hold_frame(image: Path, dest: Path, *, duration_ms: int, fps: int) -> Path:
    """Hold a single still for ``duration_ms`` -- Tier 0's whole clip. Returns ``dest``."""
    duration_s = duration_ms / 1000
    await run_ffmpeg(
        [
            "-y",
            "-loop",
            "1",
            "-i",
            str(image),
            "-t",
            f"{duration_s:.3f}",
            "-r",
            str(fps),
            "-vf",
            _EVEN_DIMENSIONS_FILTER,
            "-pix_fmt",
            "yuv420p",
            "-c:v",
            "libx264",
            str(dest),
        ],
        context=f"hold_frame {image}",
    )
    return dest


async def crossfade(images: Sequence[Path], dest: Path, *, duration_ms: int, fps: int) -> Path:
    """Crossfade ``images`` in order across ``duration_ms`` -- Tier 1's whole clip.

    Transitions land at even fractions of the total duration (``k/N`` for the k-th of N-1
    transitions), which is what falls out of holding each image for an equal slice. Each input is
    looped long enough to cover every transition it participates in; the chain's own natural
    length always lands at or past ``duration_ms`` by construction, and the final ``-t`` trims it
    to exactly that mark regardless of ffmpeg's own frame-boundary rounding -- the same trust-the-
    final-trim discipline ``hold_frame`` uses, not a promise that the internal arithmetic is exact.

    Raises:
        ValueError: fewer than one image.
    """
    if not images:
        raise ValueError("crossfade needs at least one image")

    duration_s = duration_ms / 1000
    if len(images) == 1:
        return await hold_frame(images[0], dest, duration_ms=duration_ms, fps=fps)

    n = len(images)
    xfade_dur = min(0.5, duration_s / (2 * n))
    input_dur = duration_s + xfade_dur + 0.1  # buffer past its last use in the chain

    args: list[str] = ["-y"]
    for image in images:
        args += ["-loop", "1", "-t", f"{input_dur:.3f}", "-i", str(image)]

    filters: list[str] = [f"[{i}:v]{_EVEN_DIMENSIONS_FILTER}[s{i}]" for i in range(n)]
    label = "s0"
    for k in range(1, n):
        offset = k * duration_s / n
        out_label = f"x{k}" if k < n - 1 else "vout"
        filters.append(
            f"[{label}][s{k}]xfade=transition=fade:duration={xfade_dur:.3f}:"
            f"offset={offset:.3f}[{out_label}]"
        )
        label = out_label

    args += [
        "-filter_complex",
        ";".join(filters),
        "-map",
        "[vout]",
        "-t",
        f"{duration_s:.3f}",
        "-r",
        str(fps),
        "-pix_fmt",
        "yuv420p",
        "-c:v",
        "libx264",
        str(dest),
    ]
    await run_ffmpeg(args, context=f"crossfade {n} images")
    return dest
