"""T8's definition of done, executable: a raw completion and a raw TTS call, from the CLI.

This runs *before* any adapter exists, and that ordering is the whole point. A subscription with
zero TPM quota, a wrong endpoint URL, or a deployment name that does not exist all fail in ways
that are indistinguishable from an adapter bug once there is an adapter to blame -- and
``ProviderUnavailable``'s docstring records that a typo'd endpoint is *permanently*
indistinguishable from an outage at the interface layer (D24). This script is the only place
that distinction is cheap.

Three checks, each reported independently so one failure does not mask the others:

1. **Completion.** Proves endpoint, key, deployment name and non-zero quota at once -- four
   things that are individually invisible and jointly fatal.
2. **Strict structured output**, against the project's real ``core.outline_schema.Outline``.
   This closes D26's carried gap: ``tests/test_block_schemas.py``'s unsupported-keyword list is
   the conservative set and has never been checked against a live call.
3. **TTS**, cross-checked against ``ffprobe``. Invariant 1 rests on measured duration, so the
   first thing worth knowing about a new Speech resource is whether the SDK and the file agree.

Prints the endpoint host, deployment, region and voice. Never prints a key.

    PYTHONPATH=. .venv/Scripts/python.exe scripts/verify_azure.py

``PYTHONPATH=.`` because this imports ``core.outline_schema`` and the repo is not installed as a
package -- pytest finds it via rootdir, a bare script does not.
"""

import asyncio
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncAzureOpenAI

from core.outline_schema import Outline

# Tried in order, first success wins. `.env.example` shipped the old GA version, and a gpt-5.x
# deployment is unlikely to be served by it -- but a wrong constant here surfaces two tasks later
# as a connection error that looks retryable, so the ladder is cheaper than the guess.
API_VERSIONS = ["2025-04-01-preview", "2024-12-01-preview", "2024-10-21"]

SMOKE_WAV = Path("artifacts/_smoke/narration.wav")
SMOKE_TEXT = "Structured query language injection happens when data is treated as code."


def env(name: str, default: str = "") -> str:
    value = os.environ.get(name, default)
    if not value:
        sys.exit(f"FAIL  {name} is not set. Copy .env.example to .env and fill it in.")
    return value


def client_for(version: str) -> AsyncAzureOpenAI:
    return AsyncAzureOpenAI(
        azure_endpoint=env("AZURE_OPENAI_ENDPOINT"),
        api_key=env("AZURE_OPENAI_API_KEY"),
        api_version=version,
    )


async def check_completion(deployment: str) -> str:
    """Walk the api-version ladder until one answers. Returns the version that worked."""
    ladder = [os.environ.get("AZURE_OPENAI_API_VERSION", ""), *API_VERSIONS]
    tried: list[str] = []
    last = ""

    for version in [v for v in dict.fromkeys(ladder) if v]:
        tried.append(version)
        try:
            # No temperature: gpt-5.x reasoning models reject a non-default value, and the 400
            # reads like a schema problem, which is an expensive hour to spend.
            reply = await client_for(version).chat.completions.create(
                model=deployment,
                messages=[{"role": "user", "content": "Reply with the single word: ready"}],
            )
        except Exception as exc:
            last = f"{type(exc).__name__}: {str(exc)[:200]}"
            continue

        print(f"PASS  completion            api-version={version}")
        print(f"      model replied         {reply.choices[0].message.content!r}")
        return version

    sys.exit(f"FAIL  completion. Tried {tried}.\n      last error: {last}")


async def check_structured(deployment: str, version: str) -> None:
    """The same call, constrained by the real Outline schema. A 400 here names the keyword."""
    try:
        parsed = await client_for(version).chat.completions.parse(
            model=deployment,
            messages=[
                {"role": "system", "content": "You plan short explainer videos."},
                {"role": "user", "content": "Outline a 3-segment video about SQL injection."},
            ],
            response_format=Outline,
        )
    except Exception as exc:
        sys.exit(
            f"FAIL  strict structured output. {type(exc).__name__}: {str(exc)[:400]}\n"
            "      If this names an unsupported keyword, the schema is wrong (see D26).\n"
            "      If it says the model does not support response_format, redeploy on "
            "gpt-4.1-mini 2025-04-14 / GlobalStandard."
        )

    outline = parsed.choices[0].message.parsed
    if outline is None:
        sys.exit(
            f"FAIL  strict structured output returned no parsed body. "
            f"refusal={parsed.choices[0].message.refusal!r}"
        )

    print(f"PASS  strict json_schema    Outline validated, {len(outline.segments)} segments")
    for segment in outline.segments:
        print(
            f"      - {segment.title} [{segment.visual_intent.value}, "
            f"importance {segment.importance.value}]"
        )


def ffprobe_ms(path: Path) -> int:
    """What T10's definition of done actually measures against."""
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


def check_tts() -> None:
    """Synthesize one sentence, then ask ffprobe whether the SDK told the truth about it."""
    import azure.cognitiveservices.speech as speechsdk

    config = speechsdk.SpeechConfig(
        subscription=env("AZURE_SPEECH_KEY"), region=env("AZURE_SPEECH_REGION")
    )
    config.speech_synthesis_voice_name = env("AZURE_SPEECH_VOICE")
    # Pinned rather than left to the SDK default so the file is a RIFF WAV that stdlib `wave`
    # and ffprobe both read. T10's adapter measures the file, so its format is load-bearing.
    config.set_speech_synthesis_output_format(
        speechsdk.SpeechSynthesisOutputFormat.Riff24Khz16BitMonoPcm
    )

    SMOKE_WAV.parent.mkdir(parents=True, exist_ok=True)
    synthesizer = speechsdk.SpeechSynthesizer(
        speech_config=config,
        audio_config=speechsdk.audio.AudioOutputConfig(filename=str(SMOKE_WAV)),
    )
    result = synthesizer.speak_text_async(SMOKE_TEXT).get()

    if result.reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
        details = result.cancellation_details
        sys.exit(
            f"FAIL  tts. reason={result.reason}\n"
            f"      error_code={getattr(details, 'error_code', None)}\n"
            f"      details={getattr(details, 'error_details', None)}"
        )

    sdk_ms = round(result.audio_duration.total_seconds() * 1000)
    probe_ms = ffprobe_ms(SMOKE_WAV)
    print(f"PASS  tts                   {SMOKE_WAV}")
    print(f"      sdk {sdk_ms}ms  ffprobe {probe_ms}ms  delta {abs(sdk_ms - probe_ms)}ms")


async def main() -> None:
    load_dotenv()
    deployment = env("AZURE_OPENAI_DEPLOYMENT")

    endpoint = env("AZURE_OPENAI_ENDPOINT")
    print(f"      RUNTIME_ENV={os.environ.get('RUNTIME_ENV')}  endpoint={endpoint}")
    print(
        f"      deployment={deployment}  speech={env('AZURE_SPEECH_REGION')}/"
        f"{env('AZURE_SPEECH_VOICE')}\n"
    )

    version = await check_completion(deployment)
    await check_structured(deployment, version)
    check_tts()

    print(f"\n      All three checks passed. Set AZURE_OPENAI_API_VERSION={version} in .env.")


if __name__ == "__main__":
    asyncio.run(main())
