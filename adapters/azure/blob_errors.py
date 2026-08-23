"""Turning ``azure.core`` exceptions into the vocabulary in ``interfaces/errors.py``.

Shared by ``adapters/azure/storage.py`` and ``adapters/azure/skill_registry.py``, which speak to
the same service and therefore meet the same failures. A pure function over exception objects, so
the whole table is testable with no account and no network -- the same reasoning as
``adapters/azure/openai_errors.py``.

**The interesting row is the one Azure lets us get right.** ``ResourceNotFoundError`` covers both
"no such blob" and "no such container", and those have opposite meanings to a caller: a missing
blob is ``ObjectNotFound``, which the ``Storage`` contract promises for a key nobody wrote yet,
while a missing *container* is a deployment that never happened and will never happen on retry.
Azure distinguishes them in ``error_code``, so this does too. Collapsing them would make a
misconfigured container name look exactly like an ordinary cache miss on every single key.
"""

from azure.core.exceptions import (
    ClientAuthenticationError,
    HttpResponseError,
    ResourceNotFoundError,
    ServiceRequestError,
    ServiceResponseError,
)

from interfaces import (
    AdapterError,
    ObjectNotFound,
    ProviderMisconfigured,
    ProviderUnavailable,
    RateLimited,
)

# Azure's own code for "the container is not there", as opposed to "the blob is not there".
CONTAINER_NOT_FOUND = "ContainerNotFound"

# Status codes that mean the request will be refused identically every time.
PERMANENT_STATUSES = frozenset({401, 403, 404})


def translate(exc: Exception, *, container: str = "") -> AdapterError:
    """Return the ``AdapterError`` carrying ``exc``'s meaning across the boundary.

    ``container`` is used only to make the message useful when the container itself is the
    problem, which is the failure most likely to be met on a fresh deployment.
    """
    if isinstance(exc, ResourceNotFoundError):
        if _code(exc) == CONTAINER_NOT_FOUND:
            return ProviderMisconfigured(
                f"blob container {container!r} does not exist: {_message(exc)}"
            )
        return ObjectNotFound(_message(exc))

    if isinstance(exc, ClientAuthenticationError):
        return ProviderMisconfigured(f"Azure Blob refused the credentials: {_message(exc)}")

    if isinstance(exc, ServiceRequestError | ServiceResponseError):
        # Connection refused, DNS failure, a dropped response. Includes a wrong account URL,
        # which is indistinguishable from an outage here exactly as D24 documents for endpoints.
        return ProviderUnavailable(f"could not reach Azure Blob: {_message(exc)}")

    if isinstance(exc, HttpResponseError):
        status = getattr(exc, "status_code", None)
        if status == 429:
            return RateLimited(f"Azure Blob throttled the request: {_message(exc)}")
        if status in PERMANENT_STATUSES:
            return ProviderMisconfigured(f"Azure Blob refused the request: {_message(exc)}")
        return ProviderUnavailable(f"Azure Blob returned an error: {_message(exc)}")

    # Unrecognised, but it still may not escape as a vendor type. ProviderUnavailable for the
    # reason the OpenAI table's fallback uses it: wasting one attempt beats abandoning a job
    # that might well have succeeded.
    return ProviderUnavailable(f"unrecognised Azure Blob failure: {type(exc).__name__}: {exc}")


def _code(exc: Exception) -> str:
    return str(getattr(exc, "error_code", "") or "")


def _message(exc: Exception) -> str:
    """The vendor message, trimmed. Azure's bodies carry a full XML error document."""
    return str(exc).splitlines()[0][:300]
