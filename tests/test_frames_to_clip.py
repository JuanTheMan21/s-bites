"""``mux/frames_to_clip.py`` against real ffmpeg -- offline, no network. Same bargain as
``test_audio_duration.py``'s ffprobe checks: a real, local, no-network binary this project's
environment guarantees, so it runs in the default suite rather than behind ``live``/``local_live``.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

from mux.frames_to_clip import crossfade, hold_frame

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is not on PATH")

FPS = 24


def _a_png(path: Path, color: str) -> Path:
    """A tiny real PNG via ffmpeg's own `color` source -- no Pillow dependency needed."""
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c={color}:s=64x64",
            "-frames:v",
            "1",
            str(path),
        ],
        capture_output=True,
        check=True,
    )
    return path


def _ffprobe_duration_ms(path: Path) -> int:
    out = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=nw=1:nk=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    return round(float(out) * 1000)


@pytest.mark.parametrize("duration_ms", [1000, 3000, 3480])
async def test_hold_frame_produces_a_clip_of_exactly_the_requested_duration(
    tmp_path: Path, duration_ms: int
) -> None:
    image = _a_png(tmp_path / "still.png", "blue")
    dest = tmp_path / "clip.mp4"

    result = await hold_frame(image, dest, duration_ms=duration_ms, fps=FPS)

    assert result == dest
    assert dest.stat().st_size > 0
    assert _ffprobe_duration_ms(dest) == pytest.approx(duration_ms, abs=50)


@pytest.mark.parametrize("duration_ms", [2000, 5000])
async def test_crossfade_produces_a_clip_of_exactly_the_requested_duration(
    tmp_path: Path, duration_ms: int
) -> None:
    images = [
        _a_png(tmp_path / f"still-{i}.png", color)
        for i, color in enumerate(["red", "green", "blue", "yellow"])
    ]
    dest = tmp_path / "clip.mp4"

    result = await crossfade(images, dest, duration_ms=duration_ms, fps=FPS)

    assert result == dest
    assert dest.stat().st_size > 0
    assert _ffprobe_duration_ms(dest) == pytest.approx(duration_ms, abs=50)


async def test_crossfade_with_one_image_falls_back_to_a_hold(tmp_path: Path) -> None:
    image = _a_png(tmp_path / "still.png", "purple")
    dest = tmp_path / "clip.mp4"

    result = await crossfade([image], dest, duration_ms=1500, fps=FPS)

    assert result == dest
    assert _ffprobe_duration_ms(dest) == pytest.approx(1500, abs=50)


async def test_crossfade_with_no_images_raises_value_error(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="at least one image"):
        await crossfade([], tmp_path / "clip.mp4", duration_ms=1000, fps=FPS)


async def test_crossfade_at_seconds_lands_each_transition_at_the_requested_instant(
    tmp_path: Path,
) -> None:
    """T18K: a cue-aware caller can say exactly when each transition should complete, instead of
    accepting an even k/N split that has no idea a caption cue exists."""
    images = [
        _a_png(tmp_path / f"still-{i}.png", color)
        for i, color in enumerate(["red", "green", "blue"])
    ]
    dest = tmp_path / "clip.mp4"

    result = await crossfade(
        images,
        dest,
        duration_ms=6000,
        fps=FPS,
        at_seconds=[0.5, 3.0, 6.0],
        xfade_s=[0.3, 0.3],
    )

    assert result == dest
    assert _ffprobe_duration_ms(dest) == pytest.approx(6000, abs=50)


async def test_crossfade_accepts_a_hard_cut_at_one_frame(tmp_path: Path) -> None:
    """A caption-boundary transition should be a hard cut, not a real blend -- ffmpeg rejects a
    literal zero-duration xfade, so one frame is the floor."""
    images = [
        _a_png(tmp_path / f"still-{i}.png", color) for i, color in enumerate(["red", "green"])
    ]
    dest = tmp_path / "clip.mp4"

    result = await crossfade(
        images, dest, duration_ms=3000, fps=FPS, at_seconds=[0.0, 3.0], xfade_s=[0.0]
    )

    assert result == dest
    assert _ffprobe_duration_ms(dest) == pytest.approx(3000, abs=50)


async def test_crossfade_rejects_at_seconds_of_the_wrong_length(tmp_path: Path) -> None:
    images = [_a_png(tmp_path / f"still-{i}.png", c) for i, c in enumerate(["red", "green"])]

    with pytest.raises(ValueError, match="at_seconds needs 2 entries"):
        await crossfade(images, tmp_path / "clip.mp4", duration_ms=2000, fps=FPS, at_seconds=[0.0])


async def test_crossfade_rejects_xfade_s_of_the_wrong_length(tmp_path: Path) -> None:
    images = [_a_png(tmp_path / f"still-{i}.png", c) for i, c in enumerate(["red", "green"])]

    with pytest.raises(ValueError, match="xfade_s needs 1 entries"):
        await crossfade(
            images, tmp_path / "clip.mp4", duration_ms=2000, fps=FPS, xfade_s=[0.1, 0.2]
        )


async def test_crossfade_clamps_offsets_that_would_otherwise_collide(tmp_path: Path) -> None:
    """Two instants closer together than ffmpeg's filter graph can safely handle still produce a
    valid clip -- the clamp is a safety net, not a promise the caller spaced things well."""
    images = [
        _a_png(tmp_path / f"still-{i}.png", c) for i, c in enumerate(["red", "green", "blue"])
    ]
    dest = tmp_path / "clip.mp4"

    result = await crossfade(
        images,
        dest,
        duration_ms=4000,
        fps=FPS,
        at_seconds=[0.0, 0.05, 4.0],  # second transition wants to start almost immediately
        xfade_s=[0.3, 0.3],
    )

    assert result == dest
    assert _ffprobe_duration_ms(dest) == pytest.approx(4000, abs=50)


async def test_crossfade_rejects_xfade_s_given_without_at_seconds(tmp_path: Path) -> None:
    """project-reviewer: durations come from xfade_s independently of at_seconds, so giving only
    one silently mixed a custom transition length with an even-spaced offset computed for the
    other caller's schedule -- require both or neither instead."""
    images = [_a_png(tmp_path / f"still-{i}.png", c) for i, c in enumerate(["red", "green"])]

    with pytest.raises(ValueError, match="at_seconds and xfade_s must be given together"):
        await crossfade(images, tmp_path / "clip.mp4", duration_ms=2000, fps=FPS, xfade_s=[0.2])
