"""``AzureSpeechTTS``'s own policy: how many attempts, what is worth retrying, and when it measures.

Written after ``project-reviewer`` caught the adapter raising ``RateLimited`` on the *first*
throttle. ``interfaces/tts_provider.py`` documents that error as "the backend throttled the
request **and retries were exhausted**", so the version that shipped told the caller its retries
were spent when it had not made any -- and a caller believing that backs off at the job level
over a blip a few hundred milliseconds of backoff would have absorbed.

The parallel with ``tests/test_azure_retry.py`` is deliberate. Two adapters built in one session
had opposite answers to "does this retry?", which is exactly the kind of divergence that is
invisible in either file on its own.

Nothing here touches Azure. The retry policy is ours, so it is testable without the service whose
behaviour it responds to.
"""

import wave
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from adapters.azure.tts_provider import AzureSpeechTTS
from interfaces import ProviderMisconfigured, ProviderUnavailable, RateLimited
from interfaces.tts_provider import WordMark

SAMPLE_RATE_HZ = 8_000
EXPECTED_MS = 2000


def a_narrator(max_attempts: int = 3) -> AzureSpeechTTS:
    """Credentials that are never used: every test replaces the call before it happens."""
    return AzureSpeechTTS(
        speech_key="not-a-real-key",
        region="eastus",
        voice="en-US-AvaMultilingualNeural",
        max_attempts=max_attempts,
    )


@dataclass
class StubSynthesis:
    """Stands in for ``_synthesize_once``: raises the queued failures, then writes real audio.

    Writing a real WAV rather than touching a file matters for one assertion below -- that the
    duration is measured *after* the retries, from whichever attempt actually succeeded.
    """

    failures: list[Exception]
    calls: int = field(default=0)

    async def __call__(self, text: str, dest: Path, voice: str) -> list[WordMark]:
        self.calls += 1
        if self.failures:
            # A failed attempt can leave a partial file behind. Written deliberately so the
            # measurement cannot accidentally pass by reading a leftover from an earlier attempt.
            dest.write_bytes(b"partial garbage")
            raise self.failures.pop(0)

        frames = round(EXPECTED_MS / 1000 * SAMPLE_RATE_HZ)
        with wave.open(str(dest), "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(1)
            audio.setframerate(SAMPLE_RATE_HZ)
            audio.writeframes(b"\x80" * frames)
        return [WordMark(text="narration", offset_ms=0, duration_ms=EXPECTED_MS)]


@pytest.fixture
def no_waiting(monkeypatch: pytest.MonkeyPatch) -> None:
    """Backoff is real; here it would only make the suite slow."""
    monkeypatch.setattr(
        "adapters.azure.tts_provider.wait_exponential_jitter", lambda **_: lambda state: 0.0
    )


async def test_a_transient_throttle_is_survived(tmp_path: Path, no_waiting: None) -> None:
    """The finding, as a regression test. One 429 must not fail a segment."""
    narrator = a_narrator(max_attempts=3)
    stub = StubSynthesis(failures=[RateLimited("slow down")])
    narrator._synthesize_once = stub  # type: ignore[method-assign]

    result = await narrator.synthesize("narration", tmp_path / "narration.wav")

    assert stub.calls == 2
    assert result.duration_ms == EXPECTED_MS


async def test_the_duration_is_measured_after_the_retries(tmp_path: Path, no_waiting: None) -> None:
    """The subtle half. A failed attempt leaves a partial file, and measuring too early reads it.

    That would report a duration nobody produced -- Invariant 1's failure mode arrived at
    sideways, and one that surfaces as A/V drift at T18 rather than as an error here.
    """
    narrator = a_narrator(max_attempts=3)
    narrator._synthesize_once = StubSynthesis(  # type: ignore[method-assign]
        failures=[ProviderUnavailable("connection dropped")]
    )
    dest = tmp_path / "narration.wav"

    result = await narrator.synthesize("narration", dest)

    assert result.duration_ms == EXPECTED_MS
    assert dest.read_bytes()[:4] == b"RIFF", "the partial file was replaced, not appended to"


async def test_attempts_are_capped_and_rate_limited_still_surfaces(
    tmp_path: Path, no_waiting: None
) -> None:
    """Retrying is required; retrying forever is not. The contract wants the error *eventually*."""
    narrator = a_narrator(max_attempts=3)
    stub = StubSynthesis(failures=[RateLimited("slow down") for _ in range(5)])
    narrator._synthesize_once = stub  # type: ignore[method-assign]

    with pytest.raises(RateLimited):
        await narrator.synthesize("narration", tmp_path / "narration.wav")
    assert stub.calls == 3


async def test_an_unreachable_backend_is_retried(tmp_path: Path, no_waiting: None) -> None:
    """``ProviderUnavailable`` says "retry may help", so the adapter has to actually try."""
    narrator = a_narrator(max_attempts=3)
    stub = StubSynthesis(failures=[ProviderUnavailable("timeout"), ProviderUnavailable("timeout")])
    narrator._synthesize_once = stub  # type: ignore[method-assign]

    await narrator.synthesize("narration", tmp_path / "narration.wav")

    assert stub.calls == 3


async def test_a_misconfiguration_is_not_retried(tmp_path: Path, no_waiting: None) -> None:
    """An unknown voice or a revoked key fails identically every time.

    The mirror of ``test_azure_retry.py``'s equivalent, and the reason ``RETRYABLE`` lists two
    error classes rather than catching ``AdapterError`` wholesale.
    """
    narrator = a_narrator(max_attempts=3)
    stub = StubSynthesis(failures=[ProviderMisconfigured("no such voice")])
    narrator._synthesize_once = stub  # type: ignore[method-assign]

    with pytest.raises(ProviderMisconfigured):
        await narrator.synthesize("narration", tmp_path / "narration.wav")
    assert stub.calls == 1


@pytest.mark.parametrize("kwargs", [{"max_concurrency": 0}, {"max_attempts": 0}])
def test_a_nonsensical_bound_is_refused_at_construction(kwargs: dict[str, int]) -> None:
    """A zero attempt cap means never calling the backend at all, which fails silently forever."""
    with pytest.raises(ValueError, match="at least 1"):
        AzureSpeechTTS(speech_key="k", region="eastus", voice="v", **kwargs)
