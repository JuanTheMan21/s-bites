"""The fakes held to the contracts, mechanically rather than by review.

``tests/test_interfaces.py`` asserts the contracts are worth having. This asserts the fakes
actually satisfy them -- the same job the ``adapter-parity`` agent does for the real adapters at
T13, done here because every task from T14 on is tested against these and a fake that drifts from
its interface teaches wrong lessons for ten tasks before anyone notices.

Semantics live in ``test_fake_providers.py`` and ``test_fake_services.py``. What is here is the
mechanical layer: async-ness, signatures, imports, and the exception vocabulary.
"""

import ast
import inspect
from pathlib import Path

import pytest

import interfaces
from interfaces import JobQueue, LLMProvider, RenderBackend, SkillRegistry, Storage, TTSProvider
from tests.fakes import (
    FakeJobQueue,
    FakeLLMProvider,
    FakeRenderBackend,
    FakeSkillRegistry,
    FakeStorage,
    FakeTTSProvider,
)

# Each fake and the contract it claims to satisfy.
IMPLEMENTATIONS: dict[type, type] = {
    FakeLLMProvider: LLMProvider,
    FakeTTSProvider: TTSProvider,
    FakeStorage: Storage,
    FakeSkillRegistry: SkillRegistry,
    FakeJobQueue: JobQueue,
    FakeRenderBackend: RenderBackend,
}

# The boundary rule, applied to fakes because a fake is an adapter.
BANNED_IMPORT_ROOTS = {"adapters", "azure", "openai", "huggingface", "ollama", "playwright"}

# Everything a fake is allowed to raise: the shared vocabulary, plus the builtins that mean
# "the caller made a mistake". CompositionInvalid is deliberately absent -- see below.
ADAPTER_ERROR_NAMES = {
    name for name in interfaces.__all__ if name.endswith(("Error", "Limited", "NotFound"))
} | {"ProviderUnavailable", "ProviderMisconfigured", "RenderFailed"}
BUILTIN_RAISES = {"AssertionError", "AttributeError", "KeyError", "OSError", "ValueError"}

FAKES_DIR = Path(__file__).parent / "fakes"
FAKE_MODULES = sorted(FAKES_DIR.glob("*.py"))


def contracts() -> set[type]:
    """Every ABC exported from ``interfaces``, discovered rather than listed.

    Discovered so that a seventh contract -- T30 adds ``VectorStore`` -- is covered by these
    tests the day it is written, instead of the day someone remembers to update a list here.
    """
    return {
        obj
        for obj in vars(interfaces).values()
        if inspect.isclass(obj) and getattr(obj, "__abstractmethods__", None)
    }


def raised_exception_names(module: Path) -> set[str]:
    """Names of exception classes constructed in a ``raise`` in ``module``."""
    tree = ast.parse(module.read_text(encoding="utf-8"))
    return {
        node.exc.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Raise)
        and isinstance(node.exc, ast.Call)
        and isinstance(node.exc.func, ast.Name)
    }


def imported_roots(module: Path) -> set[str]:
    """Root package of every import in ``module``, via the AST rather than a text search."""
    tree = ast.parse(module.read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            roots.add(node.module.split(".")[0])
    return roots


def test_every_contract_has_a_fake() -> None:
    """A contract with no fake is a contract T14 onward cannot test offline."""
    assert contracts() == set(IMPLEMENTATIONS.values())


@pytest.mark.parametrize("fake, contract", IMPLEMENTATIONS.items(), ids=lambda c: c.__name__)
def test_the_fake_is_a_complete_implementation(fake: type, contract: type) -> None:
    """No abstract methods left over -- a partial fake fails at construction, loudly."""
    assert issubclass(fake, contract)
    assert fake.__abstractmethods__ == frozenset()
    assert isinstance(fake(), contract)


@pytest.mark.parametrize("fake, contract", IMPLEMENTATIONS.items(), ids=lambda c: c.__name__)
def test_every_method_is_async(fake: type, contract: type) -> None:
    """Trap 1 (D19). A fake with sync methods type-checks fine and dies at the first await.

    Caught at collection rather than at whichever test happened to await it first, which is
    where it would otherwise surface -- as a confusing "coroutine expected" several frames deep.
    """
    for name in contract.__abstractmethods__:
        assert inspect.iscoroutinefunction(getattr(fake, name)), f"{fake.__name__}.{name}"


@pytest.mark.parametrize("fake, contract", IMPLEMENTATIONS.items(), ids=lambda c: c.__name__)
def test_signatures_match_the_contract_exactly(fake: type, contract: type) -> None:
    """Parity in the form a machine can check: same parameters, defaults, and annotations.

    Annotation *objects* are compared, so no fake may use ``from __future__ import
    annotations`` and ``FakeLLMProvider`` must import the same ``T`` the contract uses.
    """
    for name in contract.__abstractmethods__:
        assert inspect.signature(getattr(fake, name)) == inspect.signature(
            getattr(contract, name)
        ), f"{fake.__name__}.{name} has drifted from {contract.__name__}.{name}"


@pytest.mark.parametrize("module", FAKE_MODULES, ids=lambda p: p.name)
def test_no_fake_imports_a_vendor_sdk(module: Path) -> None:
    """The boundary rule. A fake is an adapter, and an adapter's whole job is to be swappable."""
    assert not imported_roots(module) & BANNED_IMPORT_ROOTS, module.name


@pytest.mark.parametrize("module", FAKE_MODULES, ids=lambda p: p.name)
def test_no_fake_invents_an_exception_type(module: Path) -> None:
    """Trap 2. Errors come from ``interfaces/errors.py`` or are a plain caller-bug builtin.

    A fake raising something of its own means production code learns to catch a type that will
    never be thrown at it, and misses the one that will.
    """
    unexpected = raised_exception_names(module) - ADAPTER_ERROR_NAMES - BUILTIN_RAISES
    assert not unexpected, f"{module.name} raises {sorted(unexpected)}"


@pytest.mark.parametrize("module", FAKE_MODULES, ids=lambda p: p.name)
def test_no_fake_raises_composition_invalid(module: Path) -> None:
    """D23, from the other direction. ``lint`` returns findings; judging one fatal is ours.

    A backend never raises this, so a fake that does would put the exception on the wrong side
    of the boundary and hand T14's retry classifier a failure it would wrongly requeue.
    """
    assert "CompositionInvalid" not in raised_exception_names(module)
