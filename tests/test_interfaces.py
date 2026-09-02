"""T3's definition of done, asserted rather than eyeballed.

Three things have to hold for the interface layer to be worth having: the contracts are
importable under the name callers will use, they are genuinely abstract so a half-written
adapter fails loudly at construction, and no vendor type has leaked into a signature. The
last one is the whole architectural claim, and it is the one that quietly stops being true.
"""

import inspect
from abc import ABC
from typing import get_args, get_type_hints

import pytest

from interfaces import (
    AdapterError,
    CompositionInvalid,
    JobQueue,
    LLMProvider,
    ObjectNotFound,
    ProviderMisconfigured,
    ProviderUnavailable,
    QueuedJob,
    RateLimited,
    RenderBackend,
    RenderFailed,
    SkillPack,
    SkillPackNotFound,
    SkillRegistry,
    Storage,
    StructuredOutputError,
    TTSProvider,
)

# The contract, spelled out. A method losing its @abstractmethod is invisible in a diff and
# fatal in an adapter -- pinning the expected sets here is what catches it.
CONTRACTS = {
    LLMProvider: {"generate"},
    TTSProvider: {"synthesize"},
    Storage: {"put_bytes", "put_file", "get_bytes", "get_file", "exists", "url"},
    SkillRegistry: {"load", "versions", "list_packs"},
    JobQueue: {"enqueue", "dequeue", "complete", "fail"},
    RenderBackend: {"capture", "render", "lint", "validate_geometry"},
}

# Everything a *backend* can do to us. Membership says only that the failure came from
# outside this process -- whether a retry helps is per-class, under each one's `Retry:` line.
ADAPTER_ERRORS = [
    ObjectNotFound,
    ProviderMisconfigured,
    ProviderUnavailable,
    RateLimited,
    RenderFailed,
    SkillPackNotFound,
    StructuredOutputError,
]

# Everything a signature is allowed to be built from. `interfaces` covers SkillPack,
# QueuedJob and the TypeVar; anything else -- azure, openai, playwright -- fails here.
ALLOWED_ROOTS = {
    "abc",
    "builtins",
    "collections",
    "interfaces",
    "pathlib",
    "pydantic",
    "types",
    "typing",
}


def flatten(annotation: object) -> list[object]:
    """The annotation and every type argument nested inside it."""
    found = [annotation]
    for arg in get_args(annotation):
        found.extend(flatten(arg))
    return found


@pytest.mark.parametrize("contract", CONTRACTS, ids=lambda c: c.__name__)
def test_contract_is_abstract(contract: type) -> None:
    assert issubclass(contract, ABC)
    with pytest.raises(TypeError):
        contract()


@pytest.mark.parametrize(
    "contract, expected", CONTRACTS.items(), ids=lambda c: getattr(c, "__name__", "")
)
def test_abstract_methods_are_exactly_as_specified(contract: type, expected: set[str]) -> None:
    assert set(contract.__abstractmethods__) == expected


@pytest.mark.parametrize("contract", CONTRACTS, ids=lambda c: c.__name__)
def test_io_methods_are_async(contract: type) -> None:
    for name in contract.__abstractmethods__:
        assert inspect.iscoroutinefunction(getattr(contract, name)), f"{name} is not async"


@pytest.mark.parametrize("contract", CONTRACTS, ids=lambda c: c.__name__)
def test_no_vendor_types_in_signatures(contract: type) -> None:
    """The mechanical form of 'an interface must not be satisfiable by only one vendor'."""
    for name in contract.__abstractmethods__:
        hints = get_type_hints(getattr(contract, name))
        assert hints, f"{contract.__name__}.{name} has no resolvable annotations"
        for hint in hints.values():
            for part in flatten(hint):
                module = getattr(part, "__module__", None)
                if module is None:
                    continue
                root = module.split(".")[0]
                assert root in ALLOWED_ROOTS, f"{contract.__name__}.{name} leaks {module}"


@pytest.mark.parametrize("contract", CONTRACTS, ids=lambda c: c.__name__)
def test_every_method_documents_its_contract(contract: type) -> None:
    """Docstrings here are the parity spec T13 tests both adapters against, not decoration."""
    assert contract.__doc__
    for name in contract.__abstractmethods__:
        assert getattr(contract, name).__doc__, f"{contract.__name__}.{name} is undocumented"


@pytest.mark.parametrize("error", ADAPTER_ERRORS, ids=lambda e: e.__name__)
def test_errors_are_catchable_as_one_family(error: type) -> None:
    """A caller catching AdapterError catches everything an adapter may raise."""
    assert issubclass(error, AdapterError)


def test_composition_invalid_is_deliberately_outside_the_adapter_family() -> None:
    """A broken composition is our bug, not a backend's, and a requeue reproduces it exactly.

    Pinned as a test because the natural instinct when adding an error is to parent it to
    AdapterError, and doing so here would silently make T14's retry classifier requeue a
    deterministic failure until it exhausts its attempts.
    """
    assert not issubclass(CompositionInvalid, AdapterError)


@pytest.mark.parametrize("error", [*ADAPTER_ERRORS, CompositionInvalid], ids=lambda e: e.__name__)
def test_every_error_states_whether_a_retry_can_help(error: type) -> None:
    """Membership in a family does not answer this; each type has to say it itself.

    T14 classifies failures into requeue-worthy and not. That classification is only
    possible if every error carries the answer, and only the adapter that raised it knows
    -- a wrong API key and an unreachable endpoint are indistinguishable once the exception
    has crossed the boundary.
    """
    assert "Retry:" in (error.__doc__ or ""), f"{error.__name__} does not state a retry answer"


def test_value_models_are_importable_from_the_package_root() -> None:
    assert SkillPack(name="outline", version="1", content="...").metadata == {}
    assert QueuedJob(job_id="j", payload={}, receipt="r").attempt == 1
