"""``TTSProvider``, writing real WAV files so the measurement is real too."""

import wave
from collections.abc import Sequence
from pathlib import Path

from interfaces import TTSProvider
from tests.fakes.failure_injection import FailureInjector

# Small on purpose: 8 kHz 8-bit mono is 8 KB per second, so a full 15-segment job's worth of
# narration is a few megabytes of tmp_path rather than fifty. Nothing downstream listens to it.
SAMPLE_RATE_HZ = 8_000
SILENCE_BYTE = b"\x80"  # midpoint of unsigned 8-bit PCM

# Roughly conversational narration pace, used only when a test does not name a duration.
WORDS_PER_MINUTE = 150


def wav_duration_ms(path: Path) -> int:
    """Measure a WAV file the way ffprobe would. The offline stand-in for T10's tolerance check."""
    with wave.open(str(path), "rb") as audio:
        return round(audio.getnframes() / audio.getframerate() * 1000)


class FakeTTSProvider(FailureInjector, TTSProvider):
    """Narrates to a real, playable WAV and reports the duration that file actually has.

    This is the fake whose shortcut would be most expensive. ``duration_ms`` is what every
    downstream timing decision rests on (Invariant 1), so a fake returning a plausible constant
    while writing nothing -- or writing a file of unrelated length -- would let the whole
    measured-audio rule rot silently in every test that touches it, and the rot would only
    surface as A/V drift in a rendered video at T18.

    So the number is derived *from the file*: frame count is chosen first, and the returned
    duration is computed back out of it. The two cannot disagree.
    """

    def __init__(self, durations: Sequence[int] | None = None) -> None:
        self.durations = list(durations or [])
        self.calls: list[tuple[str, Path, str | None]] = []

    async def synthesize(
        self, text: str, dest: Path, *, voice: str | None = None
    ) -> tuple[Path, int]:
        self._maybe_fail("synthesize")
        self.calls.append((text, dest, voice))

        wanted_ms = self.durations.pop(0) if self.durations else estimate_ms(text)
        if wanted_ms < 0:
            # Loud, like FakeLLMProvider's empty queue: a negative duration is a fixture typo,
            # and flooring it silently would hand back a 0ms "measurement" of a real file --
            # the exact shape of the bug this fake exists to make impossible.
            raise ValueError(f"a queued duration cannot be negative, got {wanted_ms}")
        frames = max(1, round(wanted_ms / 1000 * SAMPLE_RATE_HZ))

        dest.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(dest), "wb") as audio:  # "wb" truncates, so an existing file is replaced
            audio.setnchannels(1)
            audio.setsampwidth(1)
            audio.setframerate(SAMPLE_RATE_HZ)
            audio.writeframes(SILENCE_BYTE * frames)

        return dest, round(frames / SAMPLE_RATE_HZ * 1000)


def estimate_ms(text: str) -> int:
    """A speaking-rate estimate -- legitimate *here* only because the file is then built to match.

    The rule Invariant 1 bans is estimating a duration and reporting it as measured. This picks
    how much audio to generate, which is the synthesiser's job; the duration returned to the
    caller is measured off the result.
    """
    return max(1, round(len(text.split()) / WORDS_PER_MINUTE * 60_000))
