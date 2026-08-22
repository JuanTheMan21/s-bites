"""The exception vocabulary shared by every adapter and every caller.

Vendor exceptions must never escape an adapter. Code that catches ``ProviderUnavailable``
has to catch it whether the provider behind the interface is Azure OpenAI or Ollama, and
that is only possible if the type is declared above both of them -- here, next to the
contracts rather than inside either implementation.

Translating a vendor exception into one of these is part of writing an adapter, not an
optional refinement. An SDK's own exception class reaching ``core/`` is a boundary violation
even though no import statement records it.

Two things this module is deliberate about, because both are easy to undo by accident:

**Not everything here is an** ``AdapterError``. ``CompositionInvalid`` is raised by our own
code rather than by an adapter, and sits outside the family on purpose. An error added later
for input *we* judged invalid belongs outside it too -- parenting such a thing to
``AdapterError`` because that is the only family in the file is the specific mistake this
paragraph exists to prevent.

**Membership in the family does not imply a retry will help.** Each class states its own
answer under ``Retry:``. A blanket "``AdapterError`` means requeue" rule would send a job
with a revoked API key around the queue until it exhausted its attempts, to arrive at the
message the first attempt already had.
"""


class AdapterError(Exception):
    """Base for every failure an adapter is permitted to raise.

    Catching this means the failure came from outside this process -- a backend, a network,
    a credential -- rather than from a judgement our own code made. It does **not** mean a
    retry can help; each subclass answers that for itself.
    """


class ProviderUnavailable(AdapterError):
    """The backend could not be reached.

    Retry: **may help.** The endpoint was down, timed out, or dropped the connection.

    Known limit: a wrong endpoint URL is indistinguishable from an outage at this layer --
    both surface as a failed connection, with no signal separating "does not exist" from
    "is not answering right now". So a typo in configuration arrives here rather than as
    ``ProviderMisconfigured`` and will look retryable. T8's definition of done -- a raw
    call from the command line before any adapter exists -- is what catches that, and an
    attempt cap is what bounds it if it slips through.
    """


class ProviderMisconfigured(AdapterError):
    """The backend refused the credentials, or has no such model, deployment, or voice.

    Retry: **will not help.** A wrong key, an expired key, or a name that does not exist
    fails identically on every attempt.

    Split from ``ProviderUnavailable`` because only the adapter can tell the two apart --
    both arrive as a failed call, and by the time ``core/`` sees the exception the
    distinction is unrecoverable. An interface that collapses them makes correct retry
    classification impossible downstream regardless of what policy is chosen there.
    """


class RateLimited(AdapterError):
    """The backend throttled the request and the adapter's own retries were exhausted.

    Retry: **may help**, after a delay. An adapter that retries internally raises this only
    once it has given up, so a caller seeing it should back off at the job level rather than
    retrying immediately.
    """


class StructuredOutputError(AdapterError):
    """The model's response could not be validated against the requested schema.

    Retry: **may help, but bounded.** Sampling is not deterministic, so a fresh attempt can
    succeed where one failed. A schema the model consistently cannot satisfy is a prompt or
    schema bug, though, and this is the one case the may-help/will-not-help split cannot
    express: T14 should cap it using ``QueuedJob.attempt`` rather than treat it as freely
    retryable.
    """


class ObjectNotFound(AdapterError):
    """No stored object exists behind the given key.

    Retry: **will not help** on its own. Either the key is wrong, or the write that should
    have preceded this read never happened.
    """


class SkillPackNotFound(ObjectNotFound):
    """No such skill pack, or no such version of one, is in the registry.

    Retry: **will not help.** Packs are deployed data; one absent at the start of a job is
    absent for every attempt of it.
    """


class RenderFailed(AdapterError):
    """The renderer ran and did not produce usable output.

    Retry: **may help.** Browser crashes, timeouts, and resource exhaustion are the usual
    causes, and none reproduce reliably. A composition that is genuinely malformed should
    have been caught by ``RenderBackend.lint`` and raised as ``CompositionInvalid`` instead.
    """


class CompositionInvalid(Exception):
    """A composition failed validation and was deliberately not rendered.

    Deliberately **not** an ``AdapterError``: no backend failed. ``RenderBackend.lint``
    returns findings rather than raising, so this is raised by the code that decides a
    finding is fatal -- our own, running identically on both stacks.

    Retry: **will not help.** Nothing about a requeue changes the composition, so a retry
    reproduces this exactly while consuming an attempt.
    """
