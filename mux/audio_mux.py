"""Muxing a segment's narration onto its silent rendered clip.

Every clip ``rendering/render_segment.py`` produces is silent -- Tier 0/1 via
``mux/frames_to_clip.py``, Tier 2 via ``RenderBackend.render``, neither of which ever touches
audio. This is where the segment's measured narration WAV (T10/T16) and its rendered video (T17)
become the one playable, audible clip D3's per-segment mux was designed around.
"""

from pathlib import Path

from mux.ffmpeg_run import run_ffmpeg


async def mux_audio(video: Path, audio: Path, dest: Path, *, duration_ms: int) -> Path:
    """Combine ``video`` (silent) and ``audio`` (narration) into ``dest``. Returns ``dest``.

    ``-c:v copy`` because the video is already correct -- it was rendered at exactly
    ``duration_ms`` by ``rendering/render_segment.py``, so re-encoding it here would spend time
    changing nothing. ``-t`` pins the result to ``duration_ms`` exactly regardless of either
    input's own rounding, the same "trust the final trim" discipline
    ``mux/frames_to_clip.py`` uses -- both inputs should already agree almost exactly, since the
    audio is the very file Invariant 1's measurement came from, but the trim is what makes the
    guarantee exact rather than approximate.
    """
    duration_s = duration_ms / 1000
    await run_ffmpeg(
        [
            "-y",
            "-i",
            str(video),
            "-i",
            str(audio),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-t",
            f"{duration_s:.3f}",
            str(dest),
        ],
        context=f"mux_audio {video} + {audio}",
    )
    return dest
