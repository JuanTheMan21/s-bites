"""Joining every segment's finished clip into the one final video, with a real crossfade between
segments -- a hard cut every ~25 seconds is a large part of what makes 15 independently-composed
scenes read as a slideshow rather than one continuous piece.

Each segment is muxed to its own exact duration first (``mux/audio_mux.py``), so this only has to
join, in order, blending across the cut rather than trimming to compensate for anything -- D3's
per-segment-first design still holds, this just changes how the join itself looks.

**D93, fixed here (T18A).** The first version crossfaded audio with ``acrossfade`` alongside the
video ``xfade`` -- symmetrical code, asymmetrical result: a visual dissolve reads as polish, the
same treatment on two different segments' *narration* reads as the narrator interrupting
themselves. The fix keeps the video dissolve (still real polish) but pads each non-last clip's
video tail with a held frame via ``tpad`` before crossfading, so the blend consumes only that
padding and never a frame of real narrated picture; audio is a plain, unshrunk ``concat`` with no
blending at all, so no two segments' speech ever overlaps. Padding exactly offsets what the
crossfade shrinks, so both tracks land at exactly ``sum(durations_ms)`` -- verify this by
listening, not by asserting durations, per D93's own finding: every test here checked timing
before, and timing was never the bug.

**Also varies the visual transition (T18A).** A hard-coded ``fade`` on every one of ~14 joins in a
real video was itself repetitive; the transition style now cycles through a small fixed set,
picked deterministically by join index so a re-render of the same job looks the same.
"""

import shutil
from collections.abc import Sequence
from pathlib import Path

from mux.ffmpeg_run import run_ffmpeg

DEFAULT_TRANSITION_S = 0.5

# Cycled by join index (T18A) rather than always "fade" -- all five are ordinary xfade filter
# names ffmpeg ships, chosen to read as a clean cut style rather than a gimmick: no spins, no
# heavy distortion. "dissolve" behaves like "fade" but with slightly different blend math; both
# are included because a five-way cycle reads less repetitive than a four-way one over ~14 joins.
TRANSITION_STYLES: tuple[str, ...] = ("fade", "wipeleft", "slideup", "circleopen", "dissolve")


async def concat_segments(
    clips: Sequence[Path],
    dest: Path,
    *,
    durations_ms: Sequence[int],
    transition_s: float = DEFAULT_TRANSITION_S,
) -> Path:
    """Concatenate ``clips``, in the order given, crossfading ``transition_s`` seconds of *video*
    across each join with no audio blending. Returns ``dest``.

    ``durations_ms`` is each clip's own real length, in the same order as ``clips`` -- needed to
    compute where each transition lands in the *output* video timeline (``xfade``'s ``offset``).
    Audio needs no such computation: it is a straight ``concat``, so its length is simply
    ``sum(durations_ms)`` and nothing about where a video transition falls affects it.

    Raises:
        ValueError: ``clips`` is empty, or ``clips``/``durations_ms`` disagree in length, or a
            clip is shorter than ``transition_s`` -- the video crossfade into the *next* clip
            needs at least that much of this clip's own real head to blend from (its tail is
            always safe: it is padded, never trimmed).
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

    too_short = [i for i, ms in enumerate(durations_ms) if ms / 1000 < transition_s]
    if too_short:
        raise ValueError(
            f"clips at indexes {too_short} are shorter than transition_s ({transition_s}s) and "
            "cannot supply enough real video to crossfade from"
        )

    args: list[str] = ["-y"]
    for clip in clips:
        args += ["-i", str(clip)]

    filters: list[str] = []

    # Pad every non-last clip's video tail with a held final frame (tpad, stop_mode=clone) --
    # this is the frame the crossfade actually consumes, so no real narrated picture is lost to
    # the blend. The last clip needs no padding: nothing follows it to crossfade into.
    padded_video: list[str] = []
    for i in range(len(clips)):
        if i == len(clips) - 1:
            padded_video.append(f"{i}:v")
            continue
        label = f"v{i}pad"
        filters.append(f"[{i}:v]tpad=stop_mode=clone:stop_duration={transition_s:.3f}[{label}]")
        padded_video.append(label)

    v_label = padded_video[0]
    cumulative_s = durations_ms[0] / 1000 + transition_s  # this clip's tail is now padded
    for i in range(1, len(clips)):
        offset = cumulative_s - transition_s
        last = i == len(clips) - 1
        v_out = "vout" if last else f"v{i}out"
        style = TRANSITION_STYLES[(i - 1) % len(TRANSITION_STYLES)]
        filters.append(
            f"[{v_label}][{padded_video[i]}]xfade=transition={style}:"
            f"duration={transition_s:.3f}:offset={offset:.3f}[{v_out}]"
        )
        v_label = v_out
        step = durations_ms[i] / 1000 + (0 if last else transition_s)
        cumulative_s += step - transition_s

    # Audio: a plain, unshrunk concat -- no acrossfade, no blending, so no two segments' narration
    # is ever audible at once (D93). Its length is exactly sum(durations_ms), matching the padded
    # video track above frame for frame.
    audio_inputs = "".join(f"[{i}:a]" for i in range(len(clips)))
    filters.append(f"{audio_inputs}concat=n={len(clips)}:v=0:a=1[aout]")

    args += [
        "-filter_complex",
        ";".join(filters),
        "-map",
        f"[{v_label}]",
        "-map",
        "[aout]",
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
