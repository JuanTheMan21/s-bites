"""``config.close_adapters``: best-effort shutdown, held separately from adapter *resolution*
(``tests/test_config.py``) -- split out once T34's ``events`` field pushed the combined file over
the 200-line ceiling, the same "split by responsibility" call ``rendering/compose.py`` and
``rendering/block_timing.py`` already made for the same reason.
"""

from config import Adapters, close_adapters
from tests.fakes import (
    FakeEventChannel,
    FakeJobQueue,
    FakeLLMProvider,
    FakeRenderBackend,
    FakeSkillRegistry,
    FakeStorage,
    FakeTTSProvider,
)


async def test_close_adapters_is_best_effort_when_one_aclose_fails() -> None:
    """One adapter's aclose() raising must not skip closing the rest -- found by review."""

    class FailsToClose:
        async def aclose(self) -> None:
            raise RuntimeError("boom")

    closed = []

    class ClosesFine:
        async def aclose(self) -> None:
            closed.append(self)

    bundle = Adapters(
        llm=FailsToClose(),
        tts=FakeTTSProvider(),
        storage=FakeStorage(),
        skills=FakeSkillRegistry(),
        queue=FakeJobQueue(),
        render=ClosesFine(),
        events=FakeEventChannel(),
    )

    await close_adapters(bundle)  # must not raise, and must still close `render`
    assert closed == [bundle.render]


async def test_close_adapters_skips_slots_with_no_aclose() -> None:
    """None of the fakes define aclose() (per D55) -- proof the getattr guard actually guards."""
    fake_bundle = Adapters(
        llm=FakeLLMProvider(),
        tts=FakeTTSProvider(),
        storage=FakeStorage(),
        skills=FakeSkillRegistry(),
        queue=FakeJobQueue(),
        render=FakeRenderBackend(),
        events=FakeEventChannel(),
    )

    await close_adapters(fake_bundle)  # must not raise
