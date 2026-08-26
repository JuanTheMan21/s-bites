"""``TTSProvider`` backed by Azure Speech, returning a measured duration.

**This is the one synchronous SDK in the project**, and D19 already settled what to do about it:
wrap it in ``asyncio.to_thread`` here, inside its own adapter, because accommodating a vendor is
what an adapter is for. Every other implementation of every other contract is natively async, and
the contract stays async for all of them rather than bending to the one exception.

**Failure does not arrive as an exception.** The Speech SDK reports a problem as a *result* whose
``reason`` is ``Canceled``, carrying a ``CancellationErrorCode``. Code that only guards a ``try``
around the call sees a successful return and a zero-byte file, which then measures as 0ms and
silently becomes a scene with no narration. So the translation here is a reason-code map rather
than an exception map, and the happy path is asserted explicitly instead of assumed. Setup is
the exception: building a ``SpeechConfig`` raises a bare ``RuntimeError``, which is why
``_synthesizer`` guards it separately. Both maps live in ``adapters/azure/speech_errors.py``.

**Retries live here, and the contract requires them.** ``TTSProvider.synthesize`` documents
``RateLimited`` as "the backend throttled the request *and retries were exhausted*", so raising
it on the first throttle would be a promise this adapter does not keep -- and the caller, told
retries are spent, would back off at the job level over a blip a few hundred milliseconds of
backoff would have absorbed. The retryable set is expressed in *our* error types rather than the
vendor's, which this adapter can do and ``AzureOpenAILLMProvider`` cannot: Speech reports failure
as a translated result rather than an exception, so by the time there is something to classify it
is already ``RateLimited`` or ``ProviderUnavailable`` -- the two classes whose ``Retry:`` line
says a retry may help. The table below is the single place that judgement is made.

Unlike the LLM adapter, there is no ``Retry-After`` to honour: the Speech SDK surfaces a
cancellation reason code, not response headers, so the wait is plain exponential backoff.

The output format is pinned rather than left to the SDK default so the file is a RIFF WAV that
``adapters/audio_duration.wav_duration_ms`` and ``ffprobe`` both read. T8's smoke run had the
SDK's own reported duration and ffprobe agree to the millisecond on this format.
"""

import asyncio
from pathlib import Path

import azure.cognitiveservices.speech as speechsdk
from tenacity import AsyncRetrying, RetryCallState, stop_after_attempt, wait_exponential_jitter

from adapters.audio_duration import wav_duration_ms
from adapters.azure.speech_errors import translate_cancellation, translate_setup_failure
from interfaces import ProviderUnavailable, RateLimited, TTSProvider
from interfaces.tts_provider import SynthesisResult, WordMark

# T18A: 100ns per SDK tick (Azure Speech's own unit for both audio_offset and duration), so
# dividing by this converts to milliseconds -- the same conversion the SDK's own `.duration`
# property applies internally (see speechsdk.SpeechSynthesisWordBoundaryEventArgs).
_TICKS_PER_MS = 10_000

# RIFF because both readers understand it; 24 kHz 16-bit mono because it is the format Azure's
# neural voices are produced at, so anything else is a resample we would be paying for twice.
OUTPUT_FORMAT = speechsdk.SpeechSynthesisOutputFormat.Riff24Khz16BitMonoPcm

MAX_BACKOFF_S = 30.0

# The two error classes whose `Retry:` line says a retry may help. ProviderMisconfigured is
# absent on purpose -- an unknown voice or a revoked key fails identically on every attempt, so
# retrying it spends the budget to re-learn what the first attempt already established.
RETRYABLE = (RateLimited, ProviderUnavailable)


class AzureSpeechTTS(TTSProvider):
    """Narration from Azure Speech, measured from the file it wrote.

    Constructor arguments are explicit rather than read from the environment, for the same
    reason ``AzureOpenAILLMProvider``'s are: ``config.py`` at T13 is the only module permitted to
    know which adapter is active.

    ``max_concurrency`` bounds the per-segment fan-out and ``max_attempts`` bounds the retries
    within one segment. The resource in use is S0, whose request rate is generous, but "generous"
    is not "unbounded" and ~15 segments narrating at once is exactly the shape of traffic that
    finds the limit -- which is why both bounds exist rather than just the first.
    """

    def __init__(
        self,
        speech_key: str,
        region: str,
        *,
        voice: str,
        max_concurrency: int = 4,
        max_attempts: int = 4,
    ) -> None:
        if max_concurrency < 1:
            raise ValueError(f"max_concurrency must be at least 1, got {max_concurrency}")
        if max_attempts < 1:
            raise ValueError(f"max_attempts must be at least 1, got {max_attempts}")

        self.region = region
        self.voice = voice
        self.max_attempts = max_attempts
        self._speech_key = speech_key
        self._semaphore = asyncio.Semaphore(max_concurrency)

    async def synthesize(
        self, text: str, dest: Path, *, voice: str | None = None
    ) -> SynthesisResult:
        dest.parent.mkdir(parents=True, exist_ok=True)
        retryer = AsyncRetrying(
            stop=stop_after_attempt(self.max_attempts),
            wait=wait_exponential_jitter(initial=1.0, max=MAX_BACKOFF_S),
            retry=_is_retryable,
            # The exception is already ours -- _speak translates before raising -- so there is
            # nothing left to classify and reraise hands it straight back to the caller.
            reraise=True,
        )
        async with self._semaphore:
            words = await retryer(self._synthesize_once, text, dest, voice or self.voice)

        # Duration measured after the retries, from whichever attempt succeeded. A failed
        # attempt can leave a partial file behind, and the SDK truncates on the next one, so the
        # file this measures is always the one the successful attempt wrote. Word marks come
        # straight from that same successful attempt's own callbacks (T18A) -- never estimated,
        # the same "measured, not guessed" rule duration_ms already follows.
        return SynthesisResult(audio_path=dest, duration_ms=wav_duration_ms(dest), words=words)

    async def _synthesize_once(self, text: str, dest: Path, voice: str) -> list[WordMark]:
        """One attempt, off the event loop. Returns the word marks that attempt reported.

        ``to_thread`` rather than an executor of our own: the SDK blocks on a socket for the
        length of the utterance, which is seconds, and blocking the loop there would stall every
        other segment in the same job.
        """
        return await asyncio.to_thread(self._speak, text, dest, voice)

    def _speak(self, text: str, dest: Path, voice: str) -> list[WordMark]:
        """One blocking synthesis. Raises an ``AdapterError``; never returns on a failure."""
        synthesizer = self._synthesizer(dest, voice)
        words: list[WordMark] = []
        synthesizer.synthesis_word_boundary.connect(lambda event: _collect_word(event, words))
        result = synthesizer.speak_text_async(text).get()

        if result.reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
            raise translate_cancellation(result, voice)
        return words

    def _synthesizer(self, dest: Path, voice: str) -> speechsdk.SpeechSynthesizer:
        """Build a synthesiser, or say clearly which setting is wrong.

        Separated from ``_speak`` because it is the one part of this adapter that raises a bare
        builtin rather than reporting a result. ``SpeechConfig`` with a blank region raises
        ``RuntimeError: 5`` -- no vendor type, no usable message -- and without this guard it
        would cross the boundary untranslated, which is the single thing translation exists to
        prevent. Reachable from one empty line in ``.env``, so not a hypothetical.
        """
        try:
            config = speechsdk.SpeechConfig(subscription=self._speech_key, region=self.region)
            config.speech_synthesis_voice_name = voice
            config.set_speech_synthesis_output_format(OUTPUT_FORMAT)
            return speechsdk.SpeechSynthesizer(
                speech_config=config,
                # The SDK truncates an existing file rather than appending, so a re-run of a
                # segment overwrites cleanly -- which the contract requires.
                audio_config=speechsdk.audio.AudioOutputConfig(filename=str(dest)),
            )
        except (RuntimeError, ValueError, OSError) as exc:
            # Narrow on purpose. Nothing here has touched the network, so every failure is one of
            # three settings being wrong -- and it is exactly as wrong on the next attempt, which
            # is why ProviderMisconfigured (never retried) is the honest answer.
            raise translate_setup_failure(exc, self.region, voice) from exc


def _collect_word(
    event: speechsdk.SpeechSynthesisWordBoundaryEventArgs, words: list[WordMark]
) -> None:
    """The ``synthesis_word_boundary`` callback: append one ``WordMark`` per real word.

    Filtered to ``Word`` boundaries -- the SDK also fires ``Punctuation``/``Sentence`` boundary
    events by default, and those carry no ``.text`` worth turning into a caption word.
    """
    if event.boundary_type != speechsdk.SpeechSynthesisBoundaryType.Word:
        return
    words.append(
        WordMark(
            text=event.text,
            offset_ms=event.audio_offset // _TICKS_PER_MS,
            duration_ms=round(event.duration.total_seconds() * 1000),
        )
    )


def _is_retryable(state: RetryCallState) -> bool:
    """Whether the failure that just happened is one a fresh attempt could survive.

    Expressed over ``interfaces/errors.py`` types rather than vendor ones, which is possible
    here and is not in ``AzureOpenAILLMProvider``: Speech reports failure as a result this
    adapter has already translated, so the classification exists before the retry decision does.
    """
    exc = state.outcome.exception() if state.outcome else None
    return isinstance(exc, RETRYABLE)
