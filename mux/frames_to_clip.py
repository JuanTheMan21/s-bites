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


async def crossfade(
    images: Sequence[Path],
    dest: Path,
    *,
    duration_ms: int,
    fps: int,
    at_seconds: Sequence[float] | None = None,
    xfade_s: Sequence[float] | None = None,
) -> Path:
    """Crossfade ``images`` in order across ``duration_ms`` -- Tier 1's whole clip.

    With no ``at_seconds``/``xfade_s``, transitions land at even fractions of the total duration
    (``k/N`` for the k-th of N-1 transitions) with one shared transition length -- the original
    behavior, and still what a caller with no per-image timing gets.

    ``at_seconds``/``xfade_s`` (T18K, D161): when given, transition ``k`` (joining image ``k-1``
    and image ``k``) completes exactly at ``at_seconds[k]`` instead, using ``xfade_s[k-1]`` as
    that transition's own length. ``rendering/reveal.py`` uses this to land each transition where
    a caption cue actually changes, passing a near-zero ``xfade_s`` (a hard cut, one frame) across
    a transition whose two stills carry different caption text -- so two different cues are never
    blended into one another mid-fade, which is what an even, cue-blind schedule was doing before.
    Offsets are clamped forward (never before 0, never before the previous transition has
    finished) since caller-supplied instants are real narration timing, not guaranteed
    ffmpeg-safe spacing.

    Each input is looped long enough to cover every transition it participates in; the chain's
    own natural length always lands at or past ``duration_ms`` by construction, and the final
    ``-t`` trims it to exactly that mark regardless of ffmpeg's own frame-boundary rounding -- the
    same trust-the-final-trim discipline ``hold_frame`` uses, not a promise the internal
    arithmetic is exact.

    Raises:
        ValueError: fewer than one image, or ``at_seconds``/``xfade_s`` given with a length that
            doesn't match ``images``.
    """
    if not images:
        raise ValueError("crossfade needs at least one image")

    duration_s = duration_ms / 1000
    if len(images) == 1:
        return await hold_frame(images[0], dest, duration_ms=duration_ms, fps=fps)

    n = len(images)
    if at_seconds is not None and len(at_seconds) != n:
        raise ValueError(f"at_seconds needs {n} entries (one per image), got {len(at_seconds)}")
    if xfade_s is not None and len(xfade_s) != n - 1:
        raise ValueError(f"xfade_s needs {n - 1} entries (one per transition), got {len(xfade_s)}")
    if (at_seconds is None) != (xfade_s is None):
        # T18K/project-reviewer: offsets are computed FROM at_seconds when it's given, but
        # durations come from xfade_s independently of it -- passing only one silently mixes a
        # custom transition length with an even-spaced offset computed for the OTHER caller's
        # schedule. They are a pair; require both or neither rather than mis-timing a transition
        # with no error raised.
        raise ValueError("at_seconds and xfade_s must be given together, or not at all")

    default_xfade = min(0.5, duration_s / (2 * n))
    # ffmpeg's xfade rejects a zero-length transition -- 1/fps is the shortest a "hard cut" can
    # actually be while still being a valid transition.
    min_xfade = 1 / fps
    durations = (
        [max(d, min_xfade) for d in xfade_s] if xfade_s is not None else [default_xfade] * (n - 1)
    )

    if at_seconds is not None:
        raw_offsets = [at_seconds[k] - durations[k - 1] for k in range(1, n)]
    else:
        raw_offsets = [k * duration_s / n for k in range(1, n)]
    offsets = _clamp_increasing_offsets(raw_offsets, durations)

    input_dur = duration_s + max(durations) + 0.1  # buffer past its last use in the chain

    args: list[str] = ["-y"]
    for image in images:
        args += ["-loop", "1", "-t", f"{input_dur:.3f}", "-i", str(image)]

    filters: list[str] = [f"[{i}:v]{_EVEN_DIMENSIONS_FILTER}[s{i}]" for i in range(n)]
    label = "s0"
    for k in range(1, n):
        out_label = f"x{k}" if k < n - 1 else "vout"
        filters.append(
            f"[{label}][s{k}]xfade=transition=fade:duration={durations[k - 1]:.3f}:"
            f"offset={offsets[k - 1]:.3f}[{out_label}]"
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


def _clamp_increasing_offsets(raw_offsets: list[float], durations: list[float]) -> list[float]:
    """Force each transition to start no earlier than 0 and no earlier than the previous
    transition has finished. Caller-supplied ``at_seconds`` is real cue/reveal timing, not
    guaranteed to leave enough room between two closely-spaced instants for ffmpeg's own filter
    graph -- this is the safety net, not the primary spacing decision (``rendering/still_plan.py``
    already deduplicates instants closer than its own ``MIN_SPACING_S``)."""
    offsets: list[float] = []
    floor = 0.0
    for offset_index, raw in enumerate(raw_offsets):
        offset = max(raw, floor)
        offsets.append(offset)
        floor = offset + durations[offset_index]
    return offsets
