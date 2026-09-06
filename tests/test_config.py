"""``config.py``: the resolver, held to its own definition of done.

Every dummy value below is shaped like a real one but never used over the network -- the same
offline-dummy-credentials pattern ``tests/test_azure_retry.py``'s ``a_provider()`` already
establishes: constructing ``AsyncAzureOpenAI``, ``BlobServiceClient.from_connection_string``, and
friends does not touch the network until a call is made.
"""

import pytest

import config_events
import config_queue
import config_render
from adapters.azure.event_channel import ServiceBusEventChannel
from adapters.azure.job_queue import ServiceBusJobQueue
from adapters.azure.llm_provider import AzureOpenAILLMProvider
from adapters.azure.render_backend import ContainerAppsRenderBackend
from adapters.azure.skill_registry import BlobSkillRegistry
from adapters.azure.storage import BlobStorage
from adapters.azure.tts_provider import AzureSpeechTTS
from adapters.local.event_channel import LocalEventChannel
from adapters.local.job_queue import LocalJobQueue
from adapters.local.render_backend import PlaywrightHyperFramesRenderBackend
from adapters.local.skill_registry import DiskSkillRegistry
from adapters.local.storage import DiskStorage
from config import (
    _skill_registry,
    _storage,
    build_adapters,
    close_adapters,
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
    # ServiceBusJobQueue/ServiceBusEventChannel construct a real SDK client eagerly (T34) --
    # unlike the stub this replaces, a malformed connection string now fails at construction, so
    # this dummy must actually parse: a real endpoint shape plus a syntactically valid (never
    # dialed) key, the same "shaped like a real one" bargain this file's own docstring states.
    "AZURE_SERVICE_BUS_CONNECTION_STRING": (
        "Endpoint=sb://fake.servicebus.windows.net/;"
        "SharedAccessKeyName=fake;SharedAccessKey=ZmFrZWZha2VmYWtlZmFrZWZha2U9"
    ),
    "AZURE_SERVICE_BUS_QUEUE": "video-jobs",
    "AZURE_SERVICE_BUS_TOPIC": "job-events",
    "AZURE_SERVICE_BUS_SUBSCRIPTION": "api",
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


async def test_runtime_env_azure_builds_all_seven_real_adapters() -> None:
    adapters = build_adapters(AZURE_ENV)

    assert isinstance(adapters.llm, AzureOpenAILLMProvider)
    assert isinstance(adapters.tts, AzureSpeechTTS)
    assert isinstance(adapters.storage, BlobStorage)
    assert isinstance(adapters.skills, BlobSkillRegistry)
    assert isinstance(adapters.queue, ServiceBusJobQueue)
    assert isinstance(adapters.render, ContainerAppsRenderBackend)
    assert isinstance(adapters.events, ServiceBusEventChannel)

    await close_adapters(adapters)  # must not raise, even though nothing was ever used


async def test_render_env_bridges_azure_llm_to_the_real_local_render_backend() -> None:
    """T18A closes D92 for real: RUNTIME_ENV=azure alone still resolves the render stub
    (ContainerAppsRenderBackend, still T35's), but RENDER_ENV=local lets a caller mix in the
    real local render backend without hand-editing config.py per session. This is the exact
    combination cli.py now runs standalone with."""
    bridged = {**AZURE_ENV, "RENDER_ENV": "local"}
    adapters = build_adapters(bridged)

    assert isinstance(adapters.llm, AzureOpenAILLMProvider)  # RUNTIME_ENV=azure, unaffected
    assert isinstance(adapters.render, PlaywrightHyperFramesRenderBackend)  # RENDER_ENV=local

    await close_adapters(adapters)


async def test_queue_env_bridges_azure_to_the_real_local_job_queue() -> None:
    """The same bridge as RENDER_ENV above. ServiceBusJobQueue is real as of T34, so this is no
    longer masking a stub -- QUEUE_ENV=local is now a genuinely faster local dev loop (no
    namespace round trip per enqueue/dequeue), not a workaround for anything missing."""
    bridged = {**AZURE_ENV, "QUEUE_ENV": "local"}
    adapters = build_adapters(bridged)

    assert isinstance(adapters.llm, AzureOpenAILLMProvider)  # RUNTIME_ENV=azure, unaffected
    assert isinstance(adapters.queue, LocalJobQueue)  # QUEUE_ENV=local

    await close_adapters(adapters)


async def test_events_env_bridges_azure_to_the_real_local_event_channel() -> None:
    """Same bridge shape again, for EventChannel (T34)."""
    bridged = {**AZURE_ENV, "EVENTS_ENV": "local"}
    adapters = build_adapters(bridged)

    assert isinstance(adapters.llm, AzureOpenAILLMProvider)  # RUNTIME_ENV=azure, unaffected
    assert isinstance(adapters.events, LocalEventChannel)  # EVENTS_ENV=local

    await close_adapters(adapters)


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
    assert isinstance(config_queue.resolve(LOCAL_ENV), LocalJobQueue)
    assert isinstance(config_render.resolve(LOCAL_ENV), PlaywrightHyperFramesRenderBackend)
    assert isinstance(config_events.resolve(LOCAL_ENV), LocalEventChannel)


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


def test_an_unknown_runtime_env_raises() -> None:
    with pytest.raises(RuntimeError, match="something-else"):
        build_adapters({**AZURE_ENV, "RUNTIME_ENV": "something-else"})
