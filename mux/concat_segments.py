"""Joining every segment's finished clip into the one final video, with a real crossfade between
segments -- a hard cut every ~25 seconds is a large part of what makes 15 independently-composed
scenes read as a slideshow rather than one continuous piece.

Each segment is muxed to its own exact duration first (``mux/audio_mux.py``), so this only has to
join, in order, blending across the cut rather than trimming to compensate for anything -- D3's
per-segment-first design still holds, this just changes how the join itself looks.

**Real tradeoff, accepted and documented:** ``xfade``/``acrossfade`` need to decode and re-encode
through a filter graph, so this can no longer use ``-c copy`` the way the hard-cut version did --
concat gets slower, and the final video is shorter than the naive sum of segment durations by
``(n-1) * transition_s`` by design, not drift. That's the same "the number moves a little, nothing
desyncs" territory D18 already established for the old version's AAC frame padding, just a larger
and fully predictable amount instead of an incidental one.
"""

import shutil
from collections.abc import Sequence
from pathlib import Path

from mux.ffmpeg_run import run_ffmpeg

DEFAULT_TRANSITION_S = 0.5


async def concat_segments(
    clips: Sequence[Path],
    dest: Path,
    *,
    durations_ms: Sequence[int],
    transition_s: float = DEFAULT_TRANSITION_S,
) -> Path:
    """Concatenate ``clips``, in the order given, crossfading ``transition_s`` seconds across
    each join. Returns ``dest``.

    ``durations_ms`` is each clip's own real length, in the same order as ``clips`` -- needed to
    compute where each transition lands in the *output* timeline (``xfade``'s ``offset``), since
    a chain's cumulative position depends on every prior clip's real duration, not an assumed
    shared one (unlike ``frames_to_clip.crossfade``, which crossfades several stills of one
    segment at one shared duration).

    Raises:
        ValueError: ``clips`` is empty, or ``clips``/``durations_ms`` disagree in length, or a
            clip is too short to survive its own transitions (shorter than twice
            ``transition_s`` -- there would be nothing left of it outside the blended regions).
    """
    if not clips:
        raise ValueError("concat_segments needs at least one clip")
    if len(clips) != len(durations_ms):
        raise ValueError(
            f"clips and durations_ms must be the same length, got {len(clips)} and "
            f"{len(durations_ms)}"
        )

    dest.parent.mkdir(parents=True, exist_ok=True)

    if len(clips) == 1:
        shutil.copyfile(clips[0], dest)
        return dest

    too_short = [i for i, ms in enumerate(durations_ms) if ms / 1000 < 2 * transition_s]
    if too_short:
        raise ValueError(
            f"clips at indexes {too_short} are shorter than 2x transition_s ({transition_s}s) "
            "and cannot survive their own crossfades"
        )

    args: list[str] = ["-y"]
    for clip in clips:
        args += ["-i", str(clip)]

    filters: list[str] = []
    v_label, a_label = "0:v", "0:a"
    cumulative_s = durations_ms[0] / 1000
    for i in range(1, len(clips)):
        offset = cumulative_s - transition_s
        last = i == len(clips) - 1
        v_out, a_out = ("vout", "aout") if last else (f"v{i}", f"a{i}")
        filters.append(
            f"[{v_label}][{i}:v]xfade=transition=fade:duration={transition_s:.3f}:"
            f"offset={offset:.3f}[{v_out}]"
        )
        filters.append(f"[{a_label}][{i}:a]acrossfade=d={transition_s:.3f}[{a_out}]")
        v_label, a_label = v_out, a_out
        cumulative_s += durations_ms[i] / 1000 - transition_s

    args += [
        "-filter_complex",
        ";".join(filters),
        "-map",
        f"[{v_label}]",
        "-map",
        f"[{a_label}]",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        str(dest),
    ]
    await run_ffmpeg(args, context=f"concat_segments {len(clips)} clips with crossfade")
    return dest
