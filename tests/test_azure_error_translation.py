"""Every vendor exception the Azure adapters can meet, and the error it must become.

This is where the adapters' contribution to retry classification is actually pinned. A live test
can only ever exercise the branch the backend happens to take on the day it runs -- it will never
produce a 403, a truncated body and a 429 in one session -- while the translation itself is a
pure function over exception types that import perfectly well with no network.

The assertions are about *which* error, not about the message, because the error class is what
T14 will branch on. D24's argument in test form: a distinction the adapter collapses is a
distinction no downstream policy can recover.
"""

import httpx
import openai
import pytest
from pydantic import BaseModel, ValidationError

from adapters.azure.openai_errors import translate
from interfaces import (
    AdapterError,
    ProviderMisconfigured,
    ProviderUnavailable,
    RateLimited,
    StructuredOutputError,
)


def a_response(status: int, body: str = "{}") -> httpx.Response:
    """A real httpx response, because openai's status errors carry one and read from it."""
    return httpx.Response(
        status_code=status,
        request=httpx.Request("POST", "https://skill-bites.cognitiveservices.azure.com/"),
        text=body,
    )


def status_error(cls: type, status: int, message: str = "boom") -> Exception:
    return cls(message=message, response=a_response(status), body=None)


def a_validation_error() -> ValidationError:
    class Model(BaseModel):
        count: int

    with pytest.raises(ValidationError) as caught:
        Model(count="not a number")
    return caught.value


# The table from the module docstring of adapters/azure/openai_errors.py, as assertions.
CASES: list[tuple[str, Exception, type[AdapterError]]] = [
    ("429 throttled", status_error(openai.RateLimitError, 429), RateLimited),
    ("401 bad key", status_error(openai.AuthenticationError, 401), ProviderMisconfigured),
    ("403 forbidden", status_error(openai.PermissionDeniedError, 403), ProviderMisconfigured),
    ("404 no deployment", status_error(openai.NotFoundError, 404), ProviderMisconfigured),
    ("500 server error", status_error(openai.InternalServerError, 500), ProviderUnavailable),
    (
        "connection refused",
        openai.APIConnectionError(request=httpx.Request("POST", "https://nope.invalid/")),
        ProviderUnavailable,
    ),
    (
        "timeout",
        openai.APITimeoutError(request=httpx.Request("POST", "https://nope.invalid/")),
        ProviderUnavailable,
    ),
    ("body failed validation", a_validation_error(), StructuredOutputError),
]


@pytest.mark.parametrize("case, exc, expected", CASES, ids=[c[0] for c in CASES])
def test_the_translation_table(case: str, exc: Exception, expected: type[AdapterError]) -> None:
    assert isinstance(translate(exc), expected)


def test_a_400_about_the_schema_is_misconfiguration_not_a_bad_response() -> None:
    """The row worth defending. Azure rejecting a schema means the model never ran.

    ``StructuredOutputError`` promises a fresh attempt can succeed. That is false for a schema
    outside strict mode's supported subset -- it is rejected identically forever -- so routing it
    there would burn every attempt T14 grants to arrive at the message the first one already had.
    """
    exc = status_error(
        openai.BadRequestError,
        400,
        "Invalid schema for response_format 'Outline': 'maxLength' is not permitted.",
    )
    assert isinstance(translate(exc), ProviderMisconfigured)


def test_a_400_that_is_not_about_the_schema_stays_retryable_but_bounded() -> None:
    """A bad request this *schema* provoked is a different question from a rejected schema."""
    exc = status_error(openai.BadRequestError, 400, "messages[0].content is too long")
    assert isinstance(translate(exc), StructuredOutputError)


def test_an_unrecognised_failure_still_crosses_the_boundary_as_ours() -> None:
    """No vendor type may escape, including one this table has never seen.

    ``ProviderUnavailable`` rather than a bare ``AdapterError``: an unknown backend failure is
    better described by the retry answer that wastes one attempt than by the one that abandons a
    job which might well have succeeded.
    """
    translated = translate(RuntimeError("something new in the SDK"))

    assert isinstance(translated, ProviderUnavailable)
    assert "RuntimeError" in str(translated)


@pytest.mark.parametrize("case, exc, expected", CASES, ids=[c[0] for c in CASES])
def test_nothing_returns_a_vendor_type(case: str, exc: Exception, expected: type) -> None:
    """The boundary rule, from the other side: callers catch ours or they are not portable."""
    translated = translate(exc)

    assert isinstance(translated, AdapterError)
    assert not type(translated).__module__.startswith(("openai", "httpx", "azure"))
