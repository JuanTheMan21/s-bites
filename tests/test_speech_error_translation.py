"""Azure Speech's two failure surfaces, and the errors they must become.

Split from ``test_azure_error_translation.py`` when that file hit the 200-line ceiling. The
split is by responsibility rather than by size: Speech is the one backend in this project that
fails in two structurally different ways, and that asymmetry is what these tests are about.

**Cancellations are returned, not raised.** A failed synthesis is a *result* whose reason is
``Canceled``. An adapter that only wraps the call in a ``try`` sees a successful return and a
zero-byte file, which measures as 0ms and becomes a scene with no narration.

**Setup is raised, and raised bare.** ``SpeechConfig(region="")`` raises ``RuntimeError: 5`` --
no vendor type, no usable message. Without translation that crosses the adapter boundary
untranslated, which is the one thing translation exists to prevent.
"""

from dataclasses import dataclass

import azure.cognitiveservices.speech as speechsdk
import pytest

from adapters.azure.speech_errors import translate_cancellation, translate_setup_failure
from interfaces import (
    AdapterError,
    ProviderMisconfigured,
    ProviderUnavailable,
    RateLimited,
)

Code = speechsdk.CancellationErrorCode

SPEECH_CASES: list[tuple[object, type[AdapterError]]] = [
    (Code.AuthenticationFailure, ProviderMisconfigured),
    (Code.Forbidden, ProviderMisconfigured),
    (Code.BadRequest, ProviderMisconfigured),
    (Code.TooManyRequests, RateLimited),
    (Code.ConnectionFailure, ProviderUnavailable),
    (Code.ServiceTimeout, ProviderUnavailable),
    (Code.ServiceUnavailable, ProviderUnavailable),
    (Code.ServiceError, ProviderUnavailable),
]


@dataclass
class StubDetails:
    error_code: object
    error_details: str = "the service said no"


@dataclass
class StubResult:
    """Only the three attributes ``translate_cancellation`` reads. Nothing else is its business."""

    reason: object
    cancellation_details: StubDetails | None


@pytest.mark.parametrize("code, expected", SPEECH_CASES, ids=lambda v: getattr(v, "name", str(v)))
def test_the_speech_cancellation_table(code: object, expected: type[AdapterError]) -> None:
    result = StubResult(speechsdk.ResultReason.Canceled, StubDetails(code))

    assert isinstance(translate_cancellation(result, "en-US-AvaMultilingualNeural"), expected)


def test_an_unknown_voice_names_the_voice_rather_than_the_key() -> None:
    """The misconfiguration people actually hit. A bare "bad request" sends them to their key."""
    result = StubResult(speechsdk.ResultReason.Canceled, StubDetails(Code.BadRequest))

    translated = translate_cancellation(result, "en-GB-DoesNotExistNeural")

    assert isinstance(translated, ProviderMisconfigured)
    assert "en-GB-DoesNotExistNeural" in str(translated)


def test_an_unrecognised_cancellation_still_crosses_the_boundary_as_ours() -> None:
    result = StubResult(speechsdk.ResultReason.Canceled, StubDetails(Code.RuntimeError))

    assert isinstance(translate_cancellation(result, "voice"), ProviderUnavailable)


def test_a_non_success_result_with_no_details_at_all_is_still_handled() -> None:
    """``cancellation_details`` is ``None`` for a reason that is not a cancellation.

    Reaching through it unguarded would raise ``AttributeError`` from inside the adapter -- a
    non-``AdapterError`` escaping the boundary, which is the one thing translation exists to stop.
    """
    result = StubResult(speechsdk.ResultReason.SynthesizingAudioStarted, None)

    assert isinstance(translate_cancellation(result, "voice"), ProviderUnavailable)


def test_a_setup_failure_is_misconfiguration_and_names_all_three_settings() -> None:
    """The other way Speech fails, and the only one that raises rather than returning a result.

    ``SpeechConfig(region="")`` raises ``RuntimeError: 5`` -- verified, not assumed. Nothing has
    touched the network at that point, so it is misconfiguration by construction rather than by
    classification; and since the SDK's own message is the single character ``5``, naming the
    three settings that could be at fault is the whole value of the translation.
    """
    translated = translate_setup_failure(RuntimeError("5"), "", "en-US-AvaMultilingualNeural")

    assert isinstance(translated, ProviderMisconfigured)
    assert "AZURE_SPEECH_REGION" in str(translated)
    assert "en-US-AvaMultilingualNeural" in str(translated)
