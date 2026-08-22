"""The six contracts every adapter implements, and the errors raised around them.

``core/`` imports from here and from nowhere outside itself. Adapters implement these;
``config.py`` is the only module in the repo permitted to name a concrete implementation.
Nothing in this package may import an adapter, a vendor SDK, or ``core.models`` -- the
domain models are built on top of these contracts, not underneath them.
"""

from interfaces.errors import (
    AdapterError,
    CompositionInvalid,
    ObjectNotFound,
    ProviderMisconfigured,
    ProviderUnavailable,
    RateLimited,
    RenderFailed,
    SkillPackNotFound,
    StructuredOutputError,
)
from interfaces.job_queue import JobQueue, QueuedJob
from interfaces.llm_provider import LLMProvider
from interfaces.render_backend import RenderBackend
from interfaces.skill_registry import SkillPack, SkillRegistry
from interfaces.storage import Storage
from interfaces.tts_provider import TTSProvider

__all__ = [
    "AdapterError",
    "CompositionInvalid",
    "JobQueue",
    "LLMProvider",
    "ObjectNotFound",
    "ProviderMisconfigured",
    "ProviderUnavailable",
    "QueuedJob",
    "RateLimited",
    "RenderBackend",
    "RenderFailed",
    "SkillPack",
    "SkillPackNotFound",
    "SkillRegistry",
    "Storage",
    "StructuredOutputError",
    "TTSProvider",
]
