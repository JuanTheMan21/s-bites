"""``mux/concat_segments.py`` against real ffmpeg -- offline, no network. Same bargain as
``test_frames_to_clip.py``/``test_audio_mux.py``.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

from mux.concat_segments import concat_segments

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is not on PATH")

FPS = 24


def _a_clip(path: Path, *, color: str, duration_ms: int) -> Path:
    """A tiny real MP4 with both a video and a (silent) audio stream -- what a segment's clip
    looks like once ``mux/audio_mux.py`` has run on it."""
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c={color}:s=64x64:d={duration_ms / 1000:.3f}",
            "-f",
            "lavfi",
            "-i",
            f"anullsrc=r=8000:cl=mono:d={duration_ms / 1000:.3f}",
            "-r",
            str(FPS),
            "-pix_fmt",
            "yuv420p",
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            "-shortest",
            str(path),
        ],
        capture_output=True,
        check=True,
    )
    return path


def _ffprobe_duration_ms(path: Path, *, stream: str | None = None) -> int:
    """Container duration by default; pass ``stream="a"`` (or ``"v"``) for one track's own."""
    if stream is None:
        args = ["ffprobe", "-v", "error", "-show_entries", "format=duration"]
    else:
        args = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            stream,
            "-show_entries",
            "stream=duration",
        ]
    args += ["-of", "default=nw=1:nk=1", str(path)]
    out = subprocess.run(args, capture_output=True, text=True, check=True).stdout.strip()
    return round(float(out.splitlines()[0]) * 1000)


async def test_concat_crossfades_video_but_leaves_both_tracks_at_the_full_unshrunk_length(
    tmp_path: Path,
) -> None:
    """D93, pinned as a regression test: the old version shrank *audio* by the crossfade overlap
    (``acrossfade``), which is what let two segments' narration audibly overlap. The fix (T18A)
    pads video so its crossfade shrinkage is offset, and drops audio blending entirely -- both
    tracks should now land at exactly ``sum(durations_ms)``, not the old shrunk figure.
    """
    durations_ms = [2000, 3000, 2500]
    clips = [
        _a_clip(tmp_path / f"clip-{i}.mp4", color=color, duration_ms=duration_ms)
        for i, (color, duration_ms) in enumerate(
            zip(["red", "green", "blue"], durations_ms, strict=True)
        )
    ]
    dest = tmp_path / "final.mp4"

    result = await concat_segments(clips, dest, durations_ms=durations_ms)

    assert result == dest
    assert dest.stat().st_size > 0
    expected_ms = sum(durations_ms)
    assert _ffprobe_duration_ms(dest) == pytest.approx(expected_ms, abs=200)
    assert _ffprobe_duration_ms(dest, stream="a") == pytest.approx(expected_ms, abs=200)


async def test_concat_with_one_clip_copies_it_through_unchanged(tmp_path: Path) -> None:
    clip = _a_clip(tmp_path / "only.mp4", color="purple", duration_ms=1200)
    dest = tmp_path / "final.mp4"

    result = await concat_segments([clip], dest, durations_ms=[1200])

    assert result == dest
    assert _ffprobe_duration_ms(dest) == pytest.approx(1200, abs=100)


async def test_concat_with_no_clips_raises_value_error(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="at least one clip"):
        await concat_segments([], tmp_path / "final.mp4", durations_ms=[])


async def test_mismatched_clips_and_durations_raises_value_error(tmp_path: Path) -> None:
    clip = _a_clip(tmp_path / "a.mp4", color="red", duration_ms=1000)
    with pytest.raises(ValueError, match="same length"):
        await concat_segments([clip, clip], tmp_path / "final.mp4", durations_ms=[1000])


async def test_a_clip_too_short_for_its_own_transitions_raises_value_error(tmp_path: Path) -> None:
    short = _a_clip(tmp_path / "short.mp4", color="red", duration_ms=400)
    long = _a_clip(tmp_path / "long.mp4", color="blue", duration_ms=2000)

    with pytest.raises(ValueError, match="shorter than"):
        await concat_segments([short, long], tmp_path / "final.mp4", durations_ms=[400, 2000])
