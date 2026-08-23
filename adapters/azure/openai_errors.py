"""Turning ``openai`` exceptions into the vocabulary in ``interfaces/errors.py``.

A pure function with no client, no network and no state, so the whole table is testable offline
-- which matters because this table *is* the adapter's contribution to retry classification, and
a live test can only ever exercise the one branch the backend happens to take that day.

The principle it implements is D24's: **an interface must preserve distinctions only the adapter
can observe; what to do about them is the caller's policy.** A revoked key and a dead endpoint
both arrive here as a failed call. Once the exception crosses the boundary the difference is gone
for good, so collapsing them makes correct retry classification impossible downstream no matter
how well T14 is written.

Every mapping below is chosen by its ``Retry:`` answer rather than by which name looks closest:

===============================================  =======================  ================
openai                                           ours                     retry
===============================================  =======================  ================
``RateLimitError``                               ``RateLimited``          after a delay
``APIConnectionError`` / ``APITimeoutError``     ``ProviderUnavailable``  may help
``InternalServerError`` (5xx)                    ``ProviderUnavailable``  may help
``AuthenticationError`` (401)                    ``ProviderMisconfigured``  never
``PermissionDeniedError`` (403)                  ``ProviderMisconfigured``  never
``NotFoundError`` (404, no such deployment)      ``ProviderMisconfigured``  never
``BadRequestError`` naming the schema            ``ProviderMisconfigured``  never
``LengthFinishReasonError``                      ``StructuredOutputError``  bounded
``ValidationError`` on the parsed body           ``StructuredOutputError``  bounded
===============================================  =======================  ================

The ``BadRequestError`` row is the one worth defending. A 400 rejecting the *schema* is not the
model failing to satisfy it -- the model never ran. ``StructuredOutputError`` promises "a fresh
attempt can succeed", which is false here: a schema Azure will not accept is rejected identically
forever, and routing it there would burn every attempt T14 grants. A 400 that is *not* about the
schema stays ``StructuredOutputError``, because that is a request this schema provoked.
"""

import openai
from pydantic import ValidationError

from interfaces import (
    AdapterError,
    ProviderMisconfigured,
    ProviderUnavailable,
    RateLimited,
    StructuredOutputError,
)

# Substrings that identify a 400 as "Azure refused this schema" rather than "the model could not
# fill it". Matched case-insensitively against the message, because the shape of Azure's 400 body
# is not something a stable contract can be built on -- but its retry answer is.
SCHEMA_REJECTION_MARKERS = (
    "response_format",
    "json_schema",
    "invalid schema",
    "additionalproperties",
    "'schema'",
)


def translate(exc: Exception) -> AdapterError:
    """Return the ``AdapterError`` that carries ``exc``'s meaning across the boundary.

    Never raises and never returns ``None``: an exception this does not recognise still has to
    cross the boundary as *something* our callers can catch, and an unrecognised failure from a
    backend is best described as the backend being unavailable -- the retry answer that wastes an
    attempt rather than the one that abandons a recoverable job.
    """
    if isinstance(exc, openai.RateLimitError):
        return RateLimited(f"Azure OpenAI throttled the request: {_message(exc)}")

    if isinstance(exc, openai.APITimeoutError | openai.APIConnectionError):
        # Includes a wrong endpoint URL, which is indistinguishable from an outage here and is
        # documented as such on ProviderUnavailable. scripts/verify_azure.py is the mitigation.
        return ProviderUnavailable(f"could not reach Azure OpenAI: {_message(exc)}")

    if isinstance(exc, openai.AuthenticationError | openai.PermissionDeniedError):
        return ProviderMisconfigured(f"Azure OpenAI refused the credentials: {_message(exc)}")

    if isinstance(exc, openai.NotFoundError):
        return ProviderMisconfigured(f"no such Azure OpenAI deployment: {_message(exc)}")

    if isinstance(exc, openai.BadRequestError):
        message = _message(exc)
        if any(marker in message.lower() for marker in SCHEMA_REJECTION_MARKERS):
            return ProviderMisconfigured(f"Azure OpenAI rejected the schema: {message}")
        return StructuredOutputError(f"Azure OpenAI rejected the request: {message}")

    if isinstance(exc, openai.InternalServerError):
        return ProviderUnavailable(f"Azure OpenAI returned a server error: {_message(exc)}")

    if isinstance(exc, openai.LengthFinishReasonError):
        # The model ran out of room mid-object, so the response is truncated JSON. A retry can
        # succeed -- sampling differs -- but a schema too large for the token budget will not,
        # which is exactly the bounded case StructuredOutputError documents.
        return StructuredOutputError(
            f"the response was cut off before it satisfied the schema: {_message(exc)}"
        )

    if isinstance(exc, ValidationError):
        return StructuredOutputError(f"the response did not validate against the schema: {exc}")

    return ProviderUnavailable(f"unrecognised Azure OpenAI failure: {type(exc).__name__}: {exc}")


def _message(exc: Exception) -> str:
    """The vendor message, trimmed. Long enough to diagnose, short enough for a log line."""
    return str(exc)[:400]
