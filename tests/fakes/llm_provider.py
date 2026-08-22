"""``LLMProvider``, answering from a queue of pre-built model instances."""

from collections.abc import Sequence
from dataclasses import dataclass

from pydantic import BaseModel

from interfaces import LLMProvider, StructuredOutputError
from interfaces.llm_provider import T
from tests.fakes.failure_injection import FailureInjector


@dataclass(frozen=True, slots=True)
class LLMCall:
    """One recorded call. What was asked, of which schema, under which system instruction."""

    prompt: str
    schema: type[BaseModel]
    system: str | None


class FakeLLMProvider(FailureInjector, LLMProvider):
    """Returns queued responses in order, and records what it was asked for.

    Responses are pre-built pydantic instances rather than JSON, because parsing and validation
    live on the adapter side of the boundary: ``core/`` receives an object or an error, never a
    string that might be JSON. Synthesising a plausible instance from an arbitrary schema was
    rejected -- it would put a second, quietly diverging implementation of every schema's
    semantics inside the test suite.

    The call log is not decoration. T15's definition of done is that skill packs *demonstrably
    change behaviour*, which is an assertion about the prompt that got built, and there is
    nowhere else to observe it.
    """

    def __init__(self, responses: Sequence[BaseModel] = ()) -> None:
        self.responses = list(responses)
        self.calls: list[LLMCall] = []

    async def generate(self, prompt: str, schema: type[T], *, system: str | None = None) -> T:
        self._maybe_fail("generate")
        self.calls.append(LLMCall(prompt=prompt, schema=schema, system=system))

        if not self.responses:
            raise AssertionError(
                f"FakeLLMProvider has no response queued for a {schema.__name__} request. "
                "That is a test-authoring gap, not a backend failure -- queue one, or arm a "
                "real error with fail_next('generate', ...)."
            )

        response = self.responses.pop(0)
        if not isinstance(response, schema):
            # The real failure mode, and it catches fixture drift: a queued response built
            # against an older shape of a schema arrives here rather than passing as valid.
            raise StructuredOutputError(
                f"queued response is {type(response).__name__}, not {schema.__name__}"
            )
        return response
