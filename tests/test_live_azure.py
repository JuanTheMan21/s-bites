"""The Azure adapters against the real backends. Opt-in: ``pytest -m live``.

Everything these prove is something an offline test cannot: that the endpoint, key, deployment
and quota provisioned in T8 are the ones the adapters read; that ``gpt-5.4-mini`` really honours
strict ``json_schema`` for the project's own schemas; and that Azure Speech's measured duration
really is what ``ffprobe`` sees. The translation tables, the retry policy and the six ``Storage``
methods are all pinned offline, where they belong -- a live test exercises whichever branch the
service felt like taking that day, so it is the wrong tool for a table with nine rows.

Two of these deliberately provoke a failure. A translation table that has never met a real Azure
error is a table of guesses, and ``ProviderMisconfigured`` is the row worth confirming: it is the
one whose ``Retry:`` answer is "never", so getting it wrong costs every attempt T14 grants.

These cost money. One completion, one structured completion, and about six seconds of neural TTS
-- call it a fraction of a cent per run against the $200 credit.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

from adapters.audio_duration import wav_duration_ms
from adapters.azure.llm_provider import AzureOpenAILLMProvider
from adapters.azure.tts_provider import AzureSpeechTTS
from core.outline_schema import Outline
from interfaces import ProviderMisconfigured
from tests.azure_live import require

pytestmark = pytest.mark.live

# T10's definition of done says "within tolerance". Nothing observed so far needs any: T8's smoke
# run had the SDK and ffprobe agree exactly. 50ms is roughly one video frame at 24fps, which is
# the smallest difference that could matter to anything downstream.
TOLERANCE_MS = 50


def a_provider() -> AzureOpenAILLMProvider:
    return AzureOpenAILLMProvider(
        endpoint=require("AZURE_OPENAI_ENDPOINT"),
        api_key=require("AZURE_OPENAI_API_KEY"),
        deployment=require("AZURE_OPENAI_DEPLOYMENT"),
        api_version=require("AZURE_OPENAI_API_VERSION"),
    )


def a_narrator(voice: str | None = None) -> AzureSpeechTTS:
    return AzureSpeechTTS(
        speech_key=require("AZURE_SPEECH_KEY"),
        region=require("AZURE_SPEECH_REGION"),
        voice=voice or require("AZURE_SPEECH_VOICE"),
    )


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


async def test_llm_returns_a_validated_model_instance() -> None:
    """T9's definition of done. ``core/`` receives an object, never a string that might be JSON.

    Also the live proof that D26's conservative unsupported-keyword list is not *too* loose:
    ``Outline`` nests ``SegmentPlan`` and two enums, and strict mode rejects a bad schema with a
    400 rather than a soft warning.
    """
    provider = a_provider()
    try:
        outline = await provider.generate(
            "Outline a 3-segment explainer video about SQL injection.",
            Outline,
            system="You plan short explainer videos.",
        )
    finally:
        await provider.aclose()

    assert isinstance(outline, Outline)
    assert outline.segments, "an outline with no segments would validate and be useless"
    for plan in outline.segments:
        # Enum membership is what strict mode actually enforces for these two fields (D27), so
        # this is checking the constraint held rather than that pydantic parsed a string.
        assert plan.visual_intent in type(plan.visual_intent)
        assert plan.importance in type(plan.importance)


async def test_a_wrong_key_is_misconfiguration_not_an_outage() -> None:
    """D24's whole argument, confirmed against the real backend.

    If this arrived as ``ProviderUnavailable`` the job would be requeued until its attempts ran
    out, to arrive at the message the first attempt already had.
    """
    provider = AzureOpenAILLMProvider(
        endpoint=require("AZURE_OPENAI_ENDPOINT"),
        api_key="00000000000000000000000000000000",
        deployment=require("AZURE_OPENAI_DEPLOYMENT"),
        api_version=require("AZURE_OPENAI_API_VERSION"),
    )
    try:
        with pytest.raises(ProviderMisconfigured):
            await provider.generate("hello", Outline)
    finally:
        await provider.aclose()


@pytest.mark.skipif(shutil.which("ffprobe") is None, reason="ffprobe is not on PATH")
async def test_tts_duration_matches_ffprobe(tmp_path: Path) -> None:
    """T10's definition of done, and the number Invariant 1 rests on.

    ``ffprobe`` is the independent check precisely because it is not the code under test -- the
    adapter measures with stdlib ``wave``, so agreement here is two different readers of the
    same file rather than one reader agreeing with itself.
    """
    dest = tmp_path / "segments" / "0" / "narration.wav"
    path, duration_ms = await a_narrator().synthesize(
        "Structured query language injection happens when data is treated as code.", dest
    )

    assert path == dest and dest.is_file()
    assert duration_ms > 0
    assert abs(duration_ms - ffprobe_ms(dest)) <= TOLERANCE_MS
    assert duration_ms == wav_duration_ms(dest)


async def test_synthesize_creates_the_destination_directory(tmp_path: Path) -> None:
    """A contract term, and the one the artifact layout depends on every single segment."""
    dest = tmp_path / "does" / "not" / "exist" / "narration.wav"

    assert (await a_narrator().synthesize("One short line.", dest))[0].is_file()


async def test_an_unknown_voice_is_misconfiguration_not_an_outage(tmp_path: Path) -> None:
    """Named on ``TTSProvider.synthesize``: it fails identically on every attempt.

    Speech reports this as a *result* whose reason is Canceled, not as an exception -- so an
    adapter that only guards a ``try`` would return a zero-byte file here and let it become a
    silent scene.
    """
    narrator = a_narrator(voice="en-GB-ThisVoiceDoesNotExistNeural")

    with pytest.raises(ProviderMisconfigured, match="ThisVoiceDoesNotExist"):
        await narrator.synthesize("One short line.", tmp_path / "narration.wav")
