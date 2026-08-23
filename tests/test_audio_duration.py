"""The measurement every timing decision rests on, checked against the fake and against ffprobe.

``adapters/audio_duration.py`` is small enough to look self-evidently correct, which is exactly
the kind of module that quietly disagrees with something. Two things have to hold: it agrees with
``FakeTTSProvider``, so every timing assertion written against the fake from T14 on means the
same thing on the real stack; and it agrees with ``ffprobe``, which is what T10's definition of
done actually names.

The ffprobe check runs offline. It needs a WAV, not a network -- D38 already established that the
fake writes a real one and that ffprobe reads a 9000ms synthesis as exactly ``9.000000``.
"""

import shutil
import subprocess
import wave
from pathlib import Path

import pytest

from adapters.audio_duration import wav_duration_ms
from tests.fakes import FakeTTSProvider
from tests.fakes.tts_provider import wav_duration_ms as fake_wav_duration_ms

DURATIONS_MS = [1, 250, 1000, 3480, 9000, 28_000]


def ffprobe_ms(path: Path) -> int:
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


@pytest.mark.parametrize("wanted_ms", DURATIONS_MS)
async def test_it_measures_what_the_synthesiser_produced(tmp_path: Path, wanted_ms: int) -> None:
    dest = tmp_path / "narration.wav"
    _, reported_ms = await FakeTTSProvider([wanted_ms]).synthesize("narration", dest)

    assert wav_duration_ms(dest) == reported_ms


@pytest.mark.parametrize("wanted_ms", DURATIONS_MS)
async def test_it_agrees_with_the_fake_used_by_every_other_test(
    tmp_path: Path, wanted_ms: int
) -> None:
    """Two implementations of the same measurement, which is two chances to be wrong.

    The fake's copy cannot import this one -- ``tests/test_fakes.py`` bans ``adapters`` as an
    import root inside fakes -- so they stay separate and are held together here instead.
    """
    dest = tmp_path / "narration.wav"
    await FakeTTSProvider([wanted_ms]).synthesize("narration", dest)

    assert wav_duration_ms(dest) == fake_wav_duration_ms(dest)


@pytest.mark.skipif(shutil.which("ffprobe") is None, reason="ffprobe is not on PATH")
@pytest.mark.parametrize("wanted_ms", DURATIONS_MS)
async def test_it_agrees_with_ffprobe(tmp_path: Path, wanted_ms: int) -> None:
    """T10's definition of done, in its own words. Exact, not within tolerance.

    8 kHz is a whole multiple of 1000, so the frames-to-milliseconds arithmetic never rounds.
    """
    dest = tmp_path / "narration.wav"
    await FakeTTSProvider([wanted_ms]).synthesize("narration", dest)

    assert wav_duration_ms(dest) == ffprobe_ms(dest)


def test_a_file_that_is_not_a_wav_raises_value_error_not_an_adapter_error(
    tmp_path: Path,
) -> None:
    """We wrote these bytes. A file that will not parse is our bug, not the backend's.

    ``AdapterError`` would tell T14's retry classifier that the outside world misbehaved, and a
    requeue would reproduce it exactly -- burning attempts on a truncated write.
    """
    dest = tmp_path / "narration.wav"
    dest.write_bytes(b"this is not a RIFF header")

    with pytest.raises(ValueError, match="not a readable RIFF WAV"):
        wav_duration_ms(dest)


def test_a_zero_frame_rate_is_named_rather_than_dividing_by_zero(tmp_path: Path) -> None:
    """Otherwise it surfaces as ZeroDivisionError several frames from anything naming the file."""
    dest = tmp_path / "narration.wav"
    with wave.open(str(dest), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(1)
        audio.writeframes(b"\x00\x00")
    # `wave` refuses to *write* a zero frame rate, so it is patched into the header afterwards.
    raw = bytearray(dest.read_bytes())
    rate_at = raw.find(b"fmt ") + 12
    raw[rate_at : rate_at + 4] = (0).to_bytes(4, "little")
    dest.write_bytes(raw)

    with pytest.raises(ValueError, match="frame rate"):
        wav_duration_ms(dest)


def test_a_missing_file_raises_oserror(tmp_path: Path) -> None:
    with pytest.raises(OSError):
        wav_duration_ms(tmp_path / "never-written.wav")
