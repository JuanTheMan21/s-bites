"""``mux/audio_mux.py`` against real ffmpeg -- offline, no network. Same bargain
``test_frames_to_clip.py`` already makes: ffmpeg is a real, local, no-network binary this
project's environment guarantees, so this stays in the default suite behind a ``skipif`` rather
than ``live``/``local_live``.
"""

import shutil
import subprocess
import wave
from pathlib import Path

import pytest

from mux.audio_mux import mux_audio

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is not on PATH")

FPS = 24
SAMPLE_RATE_HZ = 8_000


def _silent_video(path: Path, *, duration_ms: int) -> Path:
    """A tiny real video-only MP4 (no audio stream) -- what every Tier 0/1/2 clip looks like
    before this module puts narration on it."""
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c=blue:s=64x64:d={duration_ms / 1000:.3f}",
            "-r",
            str(FPS),
            "-pix_fmt",
            "yuv420p",
            "-c:v",
            "libx264",
            str(path),
        ],
        capture_output=True,
        check=True,
    )
    return path


def _a_wav(path: Path, *, duration_ms: int) -> Path:
    """A real, playable WAV -- the same construction ``FakeTTSProvider`` uses."""
    frames = max(1, round(duration_ms / 1000 * SAMPLE_RATE_HZ))
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(1)
        audio.setframerate(SAMPLE_RATE_HZ)
        audio.writeframes(b"\x80" * frames)
    return path


def _ffprobe_stream_types(path: Path) -> set[str]:
    out = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "stream=codec_type",
            "-of",
            "csv=p=0",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return {line.strip() for line in out.splitlines() if line.strip()}


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


async def test_mux_audio_produces_a_clip_with_both_streams_at_the_exact_duration(
    tmp_path: Path,
) -> None:
    duration_ms = 3000
    video = _silent_video(tmp_path / "silent.mp4", duration_ms=duration_ms + 200)
    audio = _a_wav(tmp_path / "narration.wav", duration_ms=duration_ms)
    dest = tmp_path / "clip.mp4"

    result = await mux_audio(video, audio, dest, duration_ms=duration_ms)

    assert result == dest
    assert dest.stat().st_size > 0
    assert _ffprobe_stream_types(dest) == {"video", "audio"}
    assert _ffprobe_duration_ms(dest) == pytest.approx(duration_ms, abs=100)


async def test_mux_audio_trims_a_longer_video_to_the_requested_duration(tmp_path: Path) -> None:
    # The video is deliberately longer than duration_ms -- -t must still pin the result exactly,
    # the same "trust the final trim" discipline frames_to_clip.py uses.
    video = _silent_video(tmp_path / "silent.mp4", duration_ms=5000)
    audio = _a_wav(tmp_path / "narration.wav", duration_ms=2000)
    dest = tmp_path / "clip.mp4"

    await mux_audio(video, audio, dest, duration_ms=2000)

    assert _ffprobe_duration_ms(dest) == pytest.approx(2000, abs=100)
