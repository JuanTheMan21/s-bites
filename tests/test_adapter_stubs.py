"""The two T12 Azure stubs: signature-matched to their contract, and load-bearing precisely
because they raise.

The ``adapter-contract`` skill: "A stub with drifted signatures is worse than none, because it
makes the boundary look verified when it is not." This mechanically pins both halves of that --
that the stub is *not* abstract (every method is really implemented, if only to raise) and that
each method's signature matches the interface exactly -- so drift fails a test instead of waiting
for T34/T35 to discover it.
"""

import inspect
from pathlib import Path

import pytest

from adapters.azure.job_queue import ServiceBusJobQueue
from adapters.azure.render_backend import ContainerAppsRenderBackend
from interfaces import JobQueue, RenderBackend

STUBS = [
    (ServiceBusJobQueue("Endpoint=sb://x;", "video-jobs"), JobQueue),
    (ContainerAppsRenderBackend("rg", "env"), RenderBackend),
]


@pytest.mark.parametrize("stub,contract", STUBS)
def test_stub_is_concrete_and_matches_the_contract_signature(stub: object, contract: type) -> None:
    assert type(stub).__abstractmethods__ == frozenset()
    for name in contract.__abstractmethods__:
        stub_method = getattr(type(stub), name)
        contract_method = getattr(contract, name)
        assert inspect.signature(stub_method) == inspect.signature(contract_method), name
        assert inspect.iscoroutinefunction(stub_method), name


async def test_service_bus_job_queue_raises_not_implemented_naming_itself() -> None:
    queue = ServiceBusJobQueue("Endpoint=sb://x;", "video-jobs")

    with pytest.raises(NotImplementedError, match="T34"):
        await queue.enqueue("job-1", {})
    with pytest.raises(NotImplementedError, match="T34"):
        await queue.dequeue()
    with pytest.raises(NotImplementedError, match="T34"):
        await queue.complete("receipt")
    with pytest.raises(NotImplementedError, match="T34"):
        await queue.fail("receipt", "error")


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
