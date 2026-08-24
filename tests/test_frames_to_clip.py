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
