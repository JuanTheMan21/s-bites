"""In-memory implementations of all six contracts, for tests that must not touch a network.

**A fake is an adapter.** It is held to the standard the ``adapter-parity`` agent applies to the
real ones at T13: it may not import a vendor SDK, and it must match its interface in *semantics*
as well as signature -- return types, error behaviour, units. A fake that returns where the real
adapter raises does not fail a test; it quietly teaches ten tasks' worth of code to expect the
wrong thing, and the bill arrives when the real adapter appears.

Three consequences worth stating outright, because each is a mistake that type-checks:

* every method is ``async def`` (D19) -- ``tests/test_fakes.py`` pins this mechanically;
* errors come from ``interfaces/errors.py``. No fake invents an exception type, and none raises
  ``CompositionInvalid``, which is deliberately ours rather than an adapter's (D23);
* ``FakeTTSProvider`` writes a real WAV and measures it, because Invariant 1 is exactly the rule
  a convenient constant would erase.

Every fake can also be made to fail on demand -- see ``failure_injection``.
"""

from tests.fakes.failure_injection import FailureInjector
from tests.fakes.job_queue import FakeJobQueue
from tests.fakes.llm_provider import FakeLLMProvider, LLMCall
from tests.fakes.render_backend import CaptureCall, FakeRenderBackend, RenderCall
from tests.fakes.skill_registry import FakeSkillRegistry
from tests.fakes.storage import FakeStorage
from tests.fakes.tts_provider import FakeTTSProvider, wav_duration_ms

__all__ = [
    "CaptureCall",
    "FailureInjector",
    "FakeJobQueue",
    "FakeLLMProvider",
    "FakeRenderBackend",
    "FakeSkillRegistry",
    "FakeStorage",
    "FakeTTSProvider",
    "LLMCall",
    "RenderCall",
    "wav_duration_ms",
]
