"""What ``FakeLLMProvider`` and ``FakeTTSProvider`` actually do.

These two carry the sharpest traps. The LLM fake is what T15 asserts prompt construction
against; the TTS fake is where Invariant 1 would quietly rot if the duration it reports were
not the duration it wrote.
"""

from pathlib import Path

import pytest

from core import Importance, VisualIntent
from core.outline_schema import Outline, SegmentPlan
from interfaces import ProviderUnavailable, RateLimited, SkillPack, StructuredOutputError
from tests.fakes import FakeLLMProvider, FakeTTSProvider, wav_duration_ms


def an_outline(*titles: str) -> Outline:
    return Outline(
        segments=[
            SegmentPlan(
                title=title,
                summary="One idea, explained.",
                visual_intent=VisualIntent.BULLET_LIST,
                importance=Importance.NORMAL,
            )
            for title in titles
        ]
    )


async def test_the_llm_returns_queued_responses_in_order(fake_llm: FakeLLMProvider) -> None:
    first, second = an_outline("One"), an_outline("Two")
    fake_llm.responses.extend([first, second])

    assert await fake_llm.generate("outline this", Outline) is first
    assert await fake_llm.generate("again", Outline) is second


async def test_the_llm_records_what_it_was_asked(fake_llm: FakeLLMProvider) -> None:
    """T15's DoD is that skill packs demonstrably change behaviour -- observable only here."""
    fake_llm.responses.append(an_outline("One"))

    await fake_llm.generate("teach me about SQL injection", Outline, system="Be terse.")

    (call,) = fake_llm.calls
    assert call.prompt == "teach me about SQL injection"
    assert call.schema is Outline
    assert call.system == "Be terse."


async def test_a_response_of_the_wrong_shape_is_a_structured_output_error(
    fake_llm: FakeLLMProvider,
) -> None:
    """The real failure mode, and it catches a fixture built against an older schema."""
    fake_llm.responses.append(SkillPack(name="outline", version="1", content="..."))

    with pytest.raises(StructuredOutputError, match="SkillPack, not Outline"):
        await fake_llm.generate("outline this", Outline)


async def test_an_empty_queue_is_a_test_bug_not_a_backend_failure(
    fake_llm: FakeLLMProvider,
) -> None:
    """AssertionError, deliberately outside the adapter vocabulary: no backend was involved."""
    with pytest.raises(AssertionError, match="no response queued"):
        await fake_llm.generate("outline this", Outline)


async def test_an_armed_failure_fires_once_and_then_stops(fake_llm: FakeLLMProvider) -> None:
    """What T14's retry classifier needs: a call that fails, then a retry that succeeds."""
    fake_llm.responses.append(an_outline("One"))
    fake_llm.fail_next("generate", RateLimited("throttled"))

    with pytest.raises(RateLimited):
        await fake_llm.generate("outline this", Outline)
    assert await fake_llm.generate("outline this", Outline) is not None


def test_arming_a_method_that_does_not_exist_is_refused(fake_llm: FakeLLMProvider) -> None:
    """A typo would otherwise arm a failure that never fires, and the test would pass."""
    with pytest.raises(AttributeError, match="no method 'genrate'"):
        fake_llm.fail_next("genrate", RateLimited("throttled"))


async def test_the_narration_duration_is_measured_from_the_file_it_wrote(
    fake_tts: FakeTTSProvider, tmp_path: Path
) -> None:
    """Invariant 1, in the only form a fake can honour it.

    A constant here would be indistinguishable from a real measurement to every caller, and
    every timing test from T16 on would be asserting against a number nobody produced. So the
    returned value is checked against the audio itself -- the offline form of T10's DoD, which
    is the same assertion against ffprobe.
    """
    dest = tmp_path / "segments" / "0" / "narration.wav"

    result = await fake_tts.synthesize("A sentence of narration goes here.", dest)

    assert result.audio_path == dest
    assert result.audio_path.exists(), "a fake that reports a duration must have written the audio"
    assert wav_duration_ms(result.audio_path) == result.duration_ms


async def test_longer_narration_produces_longer_audio(
    fake_tts: FakeTTSProvider, tmp_path: Path
) -> None:
    """The duration varies with the text, so a test can build a realistic spread of segments."""
    short = await fake_tts.synthesize("Two words.", tmp_path / "a.wav")
    long = await fake_tts.synthesize(" ".join(["word"] * 200), tmp_path / "b.wav")

    assert 0 < short.duration_ms < long.duration_ms


async def test_an_exact_duration_can_be_requested_and_the_audio_matches_it(
    tmp_path: Path,
) -> None:
    """Tier resolution turns on specific millisecond counts, so tests need to pin them."""
    tts = FakeTTSProvider(durations=[9_000, 28_000])

    first = await tts.synthesize("Title.", tmp_path / "a.wav")
    second = await tts.synthesize("Body.", tmp_path / "b.wav")

    assert (first.duration_ms, second.duration_ms) == (9_000, 28_000)
    assert wav_duration_ms(tmp_path / "a.wav") == 9_000


async def test_a_negative_queued_duration_is_refused(tmp_path: Path) -> None:
    """A fixture typo, and flooring it would report 0ms as a measurement of a real file."""
    tts = FakeTTSProvider(durations=[-500])

    with pytest.raises(ValueError, match="cannot be negative"):
        await tts.synthesize("Narration.", tmp_path / "a.wav")


async def test_synthesising_over_an_existing_file_replaces_it(
    fake_tts: FakeTTSProvider, tmp_path: Path
) -> None:
    """Contract: the parent is created if absent and an existing file is overwritten."""
    dest = tmp_path / "narration.wav"
    dest.write_bytes(b"stale content that is not a wav file at all")

    result = await fake_tts.synthesize("Fresh narration.", dest)

    assert wav_duration_ms(dest) == result.duration_ms


async def test_the_tts_can_be_made_unavailable(fake_tts: FakeTTSProvider, tmp_path: Path) -> None:
    fake_tts.fail_next("synthesize", ProviderUnavailable("speech endpoint is down"))

    with pytest.raises(ProviderUnavailable):
        await fake_tts.synthesize("Narration.", tmp_path / "a.wav")
