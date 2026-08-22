"""The contract for structured text generation."""

from abc import ABC, abstractmethod
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMProvider(ABC):
    """Turns a prompt into a validated instance of a caller-supplied pydantic model.

    The schema is a *class*, not a dict of JSON Schema. That is what lets each adapter
    reach for its own strongest enforcement from a single signature: Azure OpenAI emits it
    as a strict ``json_schema`` response format, Ollama passes it as a format constraint.
    Serialisation, parsing, repair and validation all stay on the adapter side of the
    boundary, so ``core/`` receives an object or an error -- never a string that might be
    JSON and might not.

    Generation parameters -- model or deployment name, temperature, token limits,
    concurrency bounds -- are deliberately absent. They are adapter configuration read from
    the environment. A ``deployment`` parameter here would make this contract satisfiable by
    exactly one vendor, which is the failure mode the interface layer exists to prevent.
    """

    @abstractmethod
    async def generate(self, prompt: str, schema: type[T], *, system: str | None = None) -> T:
        """Return an instance of ``schema`` built from the model's response.

        ``system`` is an optional system-role instruction; ``None`` means the adapter's
        configured default. The returned object is always fully validated -- an adapter
        must not return a partially populated model.

        Raises:
            StructuredOutputError: the response could not satisfy ``schema``, including
                after any repair attempt the adapter makes.
            RateLimited: the backend throttled the request and retries were exhausted.
            ProviderUnavailable: the backend could not be reached.
            ProviderMisconfigured: the backend refused the credentials, or has no such
                model or deployment.
        """
