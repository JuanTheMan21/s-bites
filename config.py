"""Resolves which adapter set backs the six interfaces, from ``RUNTIME_ENV``.

The single module CLAUDE.md permits to name a concrete adapter class. Every adapter constructor
takes explicit arguments and never reads the environment itself (D51), so that this module's job
-- flipping ``RUNTIME_ENV`` and getting a different, working adapter set with no change in
``core/`` -- is not a formality. Nothing in ``core/`` imports this module, and nothing here is
reachable from there.

**``RUNTIME_ENV=local`` is genuinely incomplete, by user decision.** Ollama and Kokoro (local
``LLMProvider``/``TTSProvider``) don't exist yet and no task currently builds them (decisionlog.md
D58/D59). ``build_adapters`` says so loudly rather than silently: ``Storage``, ``SkillRegistry``,
``JobQueue`` and ``RenderBackend`` all resolve for real locally -- and are exercised directly by
``tests/test_config.py`` -- but the bundle as a whole raises under ``RUNTIME_ENV=local`` until a
future task closes that gap. Building Ollama/Kokoro themselves is out of scope here.

``close_adapters`` is where D55's open ``aclose()`` question lands: four adapters
(``AzureOpenAILLMProvider``, ``BlobStorage``, ``BlobSkillRegistry``,
``PlaywrightHyperFramesRenderBackend``) have an off-contract ``aclose()``, deliberately not on any
interface. This module is their owner, and closes whichever of the six resolved instances define
one -- generic over which four, so a future real ``ServiceBusJobQueue``/``ContainerAppsRenderBackend``
growing an ``aclose()`` at T34/T35 is closed automatically with no edit here.
"""

import asyncio
import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

import config_render
from adapters.azure.job_queue import ServiceBusJobQueue
from adapters.azure.llm_provider import AzureOpenAILLMProvider
from adapters.azure.skill_registry import BlobSkillRegistry
from adapters.azure.storage import BlobStorage
from adapters.azure.tts_provider import AzureSpeechTTS
from adapters.local.job_queue import LocalJobQueue
from adapters.local.skill_registry import DiskSkillRegistry
from adapters.local.storage import DiskStorage
from interfaces import JobQueue, LLMProvider, RenderBackend, SkillRegistry, Storage, TTSProvider

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Adapters:
    """One resolved instance per interface. A plain dataclass, not pydantic -- these are live
    objects (HTTP clients, semaphores) that are never serialized."""

    llm: LLMProvider
    tts: TTSProvider
    storage: Storage
    skills: SkillRegistry
    queue: JobQueue
    render: RenderBackend


def _env(
    name: str, env: Mapping[str, str], *, default: str | None = None, required: bool = False
) -> str:
    value = env.get(name, default if default is not None else "")
    if required and not value.strip():
        raise RuntimeError(f"{name} is not set. Copy .env.example to .env and fill it in.")
    return value


def _env_int(name: str, env: Mapping[str, str], *, default: str) -> int:
    value = _env(name, env, default=default)
    try:
        return int(value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer, got {value!r}") from exc


def _storage(env: Mapping[str, str]) -> Storage:
    if env.get("RUNTIME_ENV") == "local":
        return DiskStorage(Path(_env("LOCAL_ARTIFACT_DIR", env, default="./artifacts")))
    return BlobStorage(
        _env("AZURE_STORAGE_CONNECTION_STRING", env, required=True),
        _env("AZURE_STORAGE_CONTAINER", env, required=True),
    )


def _skill_registry(env: Mapping[str, str]) -> SkillRegistry:
    if env.get("RUNTIME_ENV") == "local":
        return DiskSkillRegistry(Path(_env("LOCAL_SKILLS_DIR", env, default="./runtime_skills")))
    return BlobSkillRegistry(
        _env("AZURE_STORAGE_CONNECTION_STRING", env, required=True),
        _env("AZURE_SKILLS_CONTAINER", env, required=True),
    )


def _job_queue(env: Mapping[str, str]) -> JobQueue:
    if env.get("RUNTIME_ENV") == "local":
        return LocalJobQueue()
    # Stub until T34 (D25) -- an empty connection string is honest, since it is never dialed.
    return ServiceBusJobQueue(
        _env("AZURE_SERVICE_BUS_CONNECTION_STRING", env),
        _env("AZURE_SERVICE_BUS_QUEUE", env, default="video-jobs"),
    )


# Render backend resolution lives in config_render.py (T18A) -- see that module's docstring for
# why splitting it out still honors "config.py is the only module naming concrete adapter
# classes" rather than quietly violating it.


def _llm_provider(env: Mapping[str, str]) -> LLMProvider:
    if env.get("RUNTIME_ENV") == "local":
        raise RuntimeError(
            "RUNTIME_ENV=local has no LLMProvider yet -- Ollama is deferred to a future task "
            "(see decisionlog.md D58/D59). Set RUNTIME_ENV=azure, or wait for that task."
        )
    return AzureOpenAILLMProvider(
        _env("AZURE_OPENAI_ENDPOINT", env, required=True),
        _env("AZURE_OPENAI_API_KEY", env, required=True),
        _env("AZURE_OPENAI_DEPLOYMENT", env, required=True),
        _env("AZURE_OPENAI_API_VERSION", env, required=True),
        max_concurrency=_env_int("AZURE_OPENAI_MAX_CONCURRENCY", env, default="4"),
    )


def _tts_provider(env: Mapping[str, str]) -> TTSProvider:
    if env.get("RUNTIME_ENV") == "local":
        raise RuntimeError(
            "RUNTIME_ENV=local has no TTSProvider yet -- Kokoro is deferred to a future task "
            "(see decisionlog.md D58/D59). Set RUNTIME_ENV=azure, or wait for that task."
        )
    return AzureSpeechTTS(
        _env("AZURE_SPEECH_KEY", env, required=True),
        _env("AZURE_SPEECH_REGION", env, required=True),
        voice=_env("AZURE_SPEECH_VOICE", env, required=True),
    )


def build_adapters(env: Mapping[str, str] | None = None) -> Adapters:
    """Resolve all six adapters from ``RUNTIME_ENV``. A full bundle, or a clear failure -- never a
    partial one, which is why ``RUNTIME_ENV=local`` fails before any of the four working local
    adapters are built rather than building them and discarding the result.
    """
    load_dotenv()
    env = env if env is not None else os.environ
    runtime = env.get("RUNTIME_ENV", "")
    if runtime not in ("local", "azure"):
        raise RuntimeError(f"RUNTIME_ENV must be 'local' or 'azure', got {runtime!r}")
    if runtime == "local":
        raise RuntimeError(
            "RUNTIME_ENV=local cannot build a full adapter set yet: LLMProvider (Ollama) and "
            "TTSProvider (Kokoro) do not exist (see decisionlog.md D58/D59). Storage, "
            "SkillRegistry, JobQueue and RenderBackend do resolve locally -- see config._storage "
            "et al -- but build_adapters() only ever returns a complete bundle."
        )
    return Adapters(
        llm=_llm_provider(env),
        tts=_tts_provider(env),
        storage=_storage(env),
        skills=_skill_registry(env),
        queue=_job_queue(env),
        render=config_render.resolve(env),
    )


async def close_adapters(adapters: Adapters) -> None:
    """Close whichever of the six resolved adapters define ``aclose()``; no-op for the rest.

    Generic over which four currently have one (D55) so a future real ``ServiceBusJobQueue`` or
    ``ContainerAppsRenderBackend`` growing an ``aclose()`` at T34/T35 is closed with no edit here.

    Best-effort: one adapter's ``aclose()`` raising must not skip closing the rest, since the
    intended caller is a shutdown path (T19's FastAPI lifespan) where leaking every later
    connection because an earlier one errored is worse than logging and moving on.
    """
    closers = [
        aclose
        for adapter in (
            adapters.llm,
            adapters.tts,
            adapters.storage,
            adapters.skills,
            adapters.queue,
            adapters.render,
        )
        if (aclose := getattr(adapter, "aclose", None)) is not None
    ]
    results = await asyncio.gather(*(close() for close in closers), return_exceptions=True)
    for result in results:
        if isinstance(result, BaseException):
            logger.error("adapter aclose() failed during shutdown: %s", result)
