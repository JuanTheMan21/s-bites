"""``config.py``: the resolver, held to its own definition of done.

Every dummy value below is shaped like a real one but never used over the network -- the same
offline-dummy-credentials pattern ``tests/test_azure_retry.py``'s ``a_provider()`` already
establishes: constructing ``AsyncAzureOpenAI``, ``BlobServiceClient.from_connection_string``, and
friends does not touch the network until a call is made.
"""

import pytest

from adapters.azure.job_queue import ServiceBusJobQueue
from adapters.azure.llm_provider import AzureOpenAILLMProvider
from adapters.azure.render_backend import ContainerAppsRenderBackend
from adapters.azure.skill_registry import BlobSkillRegistry
from adapters.azure.storage import BlobStorage
from adapters.azure.tts_provider import AzureSpeechTTS
from adapters.local.job_queue import LocalJobQueue
from adapters.local.render_backend import PlaywrightHyperFramesRenderBackend
from adapters.local.skill_registry import DiskSkillRegistry
from adapters.local.storage import DiskStorage
from config import (
    Adapters,
    _job_queue,
    _render_backend,
    _skill_registry,
    _storage,
    build_adapters,
    close_adapters,
)
from tests.fakes import (
    FakeJobQueue,
    FakeLLMProvider,
    FakeRenderBackend,
    FakeSkillRegistry,
    FakeStorage,
    FakeTTSProvider,
)

AZURE_ENV = {
    "RUNTIME_ENV": "azure",
    "AZURE_OPENAI_ENDPOINT": "https://skill-bites.openai.azure.com/",
    "AZURE_OPENAI_API_KEY": "not-a-real-key",
    "AZURE_OPENAI_DEPLOYMENT": "gpt-5.4-mini",
    "AZURE_OPENAI_API_VERSION": "2024-10-21",
    "AZURE_SPEECH_KEY": "not-a-real-key",
    "AZURE_SPEECH_REGION": "eastus",
    "AZURE_SPEECH_VOICE": "en-US-AvaMultilingualNeural",
    "AZURE_STORAGE_CONNECTION_STRING": "UseDevelopmentStorage=true",
    "AZURE_STORAGE_CONTAINER": "explainer-artifacts",
    "AZURE_SKILLS_CONTAINER": "runtime-skills",
    "AZURE_SERVICE_BUS_CONNECTION_STRING": "Endpoint=sb://x;",
    "AZURE_SERVICE_BUS_QUEUE": "video-jobs",
    "AZURE_RESOURCE_GROUP": "rg",
    "AZURE_CONTAINER_APPS_ENVIRONMENT": "env",
}

LOCAL_ENV = {
    "RUNTIME_ENV": "local",
    "LOCAL_ARTIFACT_DIR": "./artifacts",
    "LOCAL_SKILLS_DIR": "./runtime_skills",
    "RENDER_MAX_CONCURRENCY": "4",
    "RENDER_QUALITY": "standard",
}


async def test_runtime_env_azure_builds_all_six_real_adapters() -> None:
    adapters = build_adapters(AZURE_ENV)

    assert isinstance(adapters.llm, AzureOpenAILLMProvider)
    assert isinstance(adapters.tts, AzureSpeechTTS)
    assert isinstance(adapters.storage, BlobStorage)
    assert isinstance(adapters.skills, BlobSkillRegistry)
    assert isinstance(adapters.queue, ServiceBusJobQueue)
    assert isinstance(adapters.render, ContainerAppsRenderBackend)

    await close_adapters(adapters)  # must not raise, even though nothing was ever used


def test_runtime_env_local_raises_naming_the_missing_pieces() -> None:
    """Loud, not silent -- the user's explicit choice over a new stub adapter or a silent gap."""
    with pytest.raises(RuntimeError) as exc_info:
        build_adapters(LOCAL_ENV)

    message = str(exc_info.value)
    assert "Ollama" in message
    assert "Kokoro" in message


def test_each_local_builder_returns_the_local_adapter() -> None:
    """Proof the local resolution logic is correct today, even though build_adapters() can't
    expose it under RUNTIME_ENV=local until a future task closes T10 (D58/D59)."""
    assert isinstance(_storage(LOCAL_ENV), DiskStorage)
    assert isinstance(_skill_registry(LOCAL_ENV), DiskSkillRegistry)
    assert isinstance(_job_queue(LOCAL_ENV), LocalJobQueue)
    assert isinstance(_render_backend(LOCAL_ENV), PlaywrightHyperFramesRenderBackend)


def test_a_missing_required_azure_variable_fails_fast() -> None:
    incomplete = {**AZURE_ENV, "AZURE_OPENAI_API_KEY": ""}

    with pytest.raises(RuntimeError, match="AZURE_OPENAI_API_KEY"):
        build_adapters(incomplete)


def test_a_whitespace_only_required_variable_fails_fast() -> None:
    """A value present but blank must not satisfy `required` -- it would otherwise fail later,
    inside the vendor SDK, with a far less clear error."""
    incomplete = {**AZURE_ENV, "AZURE_OPENAI_API_KEY": "   "}

    with pytest.raises(RuntimeError, match="AZURE_OPENAI_API_KEY"):
        build_adapters(incomplete)


def test_a_non_numeric_concurrency_value_raises_a_clear_error() -> None:
    bad = {**AZURE_ENV, "AZURE_OPENAI_MAX_CONCURRENCY": "lots"}

    with pytest.raises(RuntimeError, match="AZURE_OPENAI_MAX_CONCURRENCY"):
        build_adapters(bad)


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
    )

    await close_adapters(fake_bundle)  # must not raise


def test_an_unknown_runtime_env_raises() -> None:
    with pytest.raises(RuntimeError, match="something-else"):
        build_adapters({**AZURE_ENV, "RUNTIME_ENV": "something-else"})
