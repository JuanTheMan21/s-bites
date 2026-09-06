"""Turning ``azure.servicebus`` exceptions into the vocabulary in ``interfaces/errors.py``.

Same shape as ``adapters/azure/blob_errors.py`` -- a pure function over exception objects, testable
with no namespace and no network.

**The interesting row here is the one the other error tables don't have.** ``MessageLockLostError``
and ``MessageAlreadySettled`` mean this process's lock on a message expired or was already settled
by another attempt -- not "the service failed," but "this message is no longer ours to settle."
``ServiceBusJobQueue.complete``/``fail`` catch those two directly and treat them as the no-op the
``JobQueue`` contract already promises for an unknown receipt, rather than routing them through
``translate`` and raising -- a second worker that already completed this job's message must not see
the first worker's late settle attempt turn into a fatal error.
"""

from azure.servicebus.exceptions import (
    MessageAlreadySettled,
    MessageLockLostError,
    MessagingEntityDisabledError,
    MessagingEntityNotFoundError,
    OperationTimeoutError,
    ServiceBusAuthenticationError,
    ServiceBusAuthorizationError,
    ServiceBusCommunicationError,
    ServiceBusConnectionError,
    ServiceBusError,
    ServiceBusQuotaExceededError,
    ServiceBusServerBusyError,
)

from interfaces import AdapterError, ProviderMisconfigured, ProviderUnavailable, RateLimited

# Settling a message we no longer hold the lock on is not a service failure -- see the module
# docstring. Exposed so ``ServiceBusJobQueue`` can catch it before this table's generic mapping
# would turn it into something that looks fatal.
LOCK_LOST_EXCEPTIONS = (MessageLockLostError, MessageAlreadySettled)


def translate(exc: Exception) -> AdapterError:
    """Return the ``AdapterError`` carrying ``exc``'s meaning across the boundary."""
    if isinstance(exc, ServiceBusAuthenticationError | ServiceBusAuthorizationError):
        return ProviderMisconfigured(f"Service Bus refused the credentials: {_message(exc)}")

    if isinstance(exc, MessagingEntityNotFoundError | MessagingEntityDisabledError):
        return ProviderMisconfigured(f"Service Bus queue/topic misconfigured: {_message(exc)}")

    if isinstance(exc, ServiceBusQuotaExceededError | ServiceBusServerBusyError):
        return RateLimited(f"Service Bus throttled the request: {_message(exc)}")

    if isinstance(exc, ServiceBusConnectionError | ServiceBusCommunicationError):
        return ProviderUnavailable(f"could not reach Service Bus: {_message(exc)}")

    if isinstance(exc, OperationTimeoutError):
        return ProviderUnavailable(f"Service Bus operation timed out: {_message(exc)}")

    if isinstance(exc, ServiceBusError):
        return ProviderUnavailable(f"Service Bus returned an error: {_message(exc)}")

    # Unrecognised, but it still may not escape as a vendor type -- same reasoning as
    # blob_errors.translate's own fallback.
    return ProviderUnavailable(f"unrecognised Service Bus failure: {type(exc).__name__}: {exc}")


def _message(exc: Exception) -> str:
    return str(exc).splitlines()[0][:300]
