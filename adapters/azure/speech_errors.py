"""Turning Azure Speech failures into the vocabulary in ``interfaces/errors.py``.

The sibling of ``openai_errors.py`` and ``blob_errors.py``, and the odd one out, because Speech
fails in **two structurally different ways** and only one of them is an exception.

**Cancellations are results, not exceptions.** A synthesis that fails comes back as a result whose
``reason`` is ``Canceled``, carrying a ``CancellationErrorCode``. Code that only guards a ``try``
around the call sees a successful return and a zero-byte file, which measures as 0ms and quietly
becomes a scene with no narration. ``translate_cancellation`` is the map for those.

**Setup genuinely raises**, and it raises *bare* builtins. ``SpeechConfig(subscription=..., region="")``
raises ``RuntimeError: 5`` -- no vendor exception type, no message worth reading, and nothing that
identifies it as coming from Azure at all. Verified, not assumed. That path is reachable from a
single blank line in ``.env``, which makes it the most likely misconfiguration in the whole
adapter and the one D24 is explicitly about: a config typo that must not look like an outage.
``translate_setup_failure`` is the map for those.

Both are free functions over plain values, so the tables are testable with no key, no client and
no network -- a live test only ever produces whichever failure the service felt like that day.
"""

import azure.cognitiveservices.speech as speechsdk

from interfaces import (
    AdapterError,
    ProviderMisconfigured,
    ProviderUnavailable,
    RateLimited,
)

Code = speechsdk.CancellationErrorCode

# Chosen by retry answer, exactly as the LLM adapter's table is. An unknown voice lands in
# BadRequest and fails identically on every attempt, which is why `TTSProvider.synthesize`'s
# docstring calls it a misconfiguration rather than an outage.
CANCELLATION_ERRORS: dict[object, type[AdapterError]] = {
    Code.AuthenticationFailure: ProviderMisconfigured,
    Code.Forbidden: ProviderMisconfigured,
    Code.BadRequest: ProviderMisconfigured,
    Code.TooManyRequests: RateLimited,
    Code.ConnectionFailure: ProviderUnavailable,
    Code.ServiceTimeout: ProviderUnavailable,
    Code.ServiceUnavailable: ProviderUnavailable,
    Code.ServiceError: ProviderUnavailable,
}


def translate_cancellation(result: speechsdk.SpeechSynthesisResult, voice: str) -> AdapterError:
    """Turn a non-success synthesis result into an ``AdapterError``."""
    details = result.cancellation_details
    code = getattr(details, "error_code", None)
    reason = getattr(details, "error_details", "") or result.reason

    error_type = CANCELLATION_ERRORS.get(code)
    if error_type is None:
        # Unknown code, and the reason may not even be Canceled. ProviderUnavailable for the same
        # reason the LLM table's fallback is: wasting one attempt beats abandoning a live job.
        return ProviderUnavailable(
            f"Azure Speech did not complete the synthesis (reason={result.reason}, "
            f"code={code}): {reason}"
        )

    if error_type is ProviderMisconfigured:
        # Named explicitly because "no such voice" is the misconfiguration people actually hit,
        # and a bare "bad request" sends them looking at their key instead.
        return error_type(
            f"Azure Speech refused the request for voice {voice!r} (code={code}): {reason}"
        )
    return error_type(f"Azure Speech synthesis failed (code={code}): {reason}")


def translate_setup_failure(exc: Exception, region: str, voice: str) -> AdapterError:
    """Turn a failure to *build* a synthesiser into ``ProviderMisconfigured``.

    Always misconfiguration, never an outage: nothing here has touched the network yet. The
    subscription key, the region and the voice are the only inputs, so a failure means one of the
    three is wrong -- and it will be exactly as wrong on the next attempt, which is why the
    adapter's retry predicate leaves this class alone.

    The message names all three inputs because the SDK's own is ``5``. Losing that context is how
    a blank ``AZURE_SPEECH_REGION`` becomes an afternoon.
    """
    return ProviderMisconfigured(
        f"could not configure Azure Speech for region {region!r} and voice {voice!r} "
        f"({type(exc).__name__}: {exc}). Check AZURE_SPEECH_REGION, AZURE_SPEECH_KEY and "
        f"AZURE_SPEECH_VOICE in .env."
    )
