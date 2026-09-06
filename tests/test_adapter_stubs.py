"""The one remaining T12 Azure stub: signature-matched to its contract, and load-bearing
precisely because it raises.

**``ServiceBusJobQueue`` graduated out of this file at T34** -- it is a real implementation now,
held to its contract by ``tests/test_job_queue_parity.py`` (behavior) and
``tests/test_config.py`` (that ``config.py`` actually resolves it), the same way every other real
adapter is. Leaving it parametrized here as a "stub" would assert something no longer true.

The ``adapter-contract`` skill: "A stub with drifted signatures is worse than none, because it
makes the boundary look verified when it is not." This mechanically pins both halves of that --
that the stub is *not* abstract (every method is really implemented, if only to raise) and that
each method's signature matches the interface exactly -- so drift fails a test instead of waiting
for T35 to discover it.
"""

import inspect
from pathlib import Path

import pytest

from adapters.azure.render_backend import ContainerAppsRenderBackend
from interfaces import RenderBackend

STUB = ContainerAppsRenderBackend("rg", "env")


def test_stub_is_concrete_and_matches_the_contract_signature() -> None:
    assert type(STUB).__abstractmethods__ == frozenset()
    for name in RenderBackend.__abstractmethods__:
        stub_method = getattr(type(STUB), name)
        contract_method = getattr(RenderBackend, name)
        assert inspect.signature(stub_method) == inspect.signature(contract_method), name
        assert inspect.iscoroutinefunction(stub_method), name


async def test_container_apps_render_backend_raises_not_implemented_naming_itself(
    tmp_path: Path,
) -> None:
    backend = ContainerAppsRenderBackend("rg", "env")
    composition = Path("composition.html")

    with pytest.raises(NotImplementedError, match="T35"):
        await backend.capture(composition, Path(tmp_path), at_seconds=[0.0])
    with pytest.raises(NotImplementedError, match="T35"):
        await backend.render(composition, Path(tmp_path) / "out.mp4", fps=24, duration_ms=1000)
    with pytest.raises(NotImplementedError, match="T35"):
        await backend.lint(composition)
    with pytest.raises(NotImplementedError, match="T35"):
        await backend.validate_geometry(composition)
