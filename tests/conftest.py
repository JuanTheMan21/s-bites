"""One fresh fake per test, for every contract.

Function-scoped on purpose. These accumulate state -- a queue of responses, a dict of objects,
a call log -- and a fake shared between tests is a test that passes or fails depending on what
ran before it. From T14 on, most of the suite depends on these, so the cost of getting the scope
wrong compounds.

``asyncio_mode = "auto"`` is set in ``pyproject.toml``, so an ``async def`` test needs no marker.
"""

import pytest

from tests.fakes import (
    FakeJobQueue,
    FakeLLMProvider,
    FakeRenderBackend,
    FakeSkillRegistry,
    FakeStorage,
    FakeTTSProvider,
)


@pytest.fixture
def fake_llm() -> FakeLLMProvider:
    """Empty response queue -- load it with the instances the test under way expects."""
    return FakeLLMProvider()


@pytest.fixture
def fake_tts() -> FakeTTSProvider:
    return FakeTTSProvider()


@pytest.fixture
def fake_storage() -> FakeStorage:
    return FakeStorage()


@pytest.fixture
def fake_skills() -> FakeSkillRegistry:
    return FakeSkillRegistry()


@pytest.fixture
def fake_queue() -> FakeJobQueue:
    return FakeJobQueue()


@pytest.fixture
def fake_render() -> FakeRenderBackend:
    return FakeRenderBackend()
