"""Shared setup for the API test suite (T23): a fully fake ``Adapters`` bundle wired into a real
FastAPI app, so the app under test is exactly what production runs -- only the six interfaces
underneath differ.
"""

from config import Adapters
from tests.fakes import FakeJobQueue, FakeRenderBackend, FakeStorage, FakeTTSProvider
from tests.graph_pipeline_fixtures import seeded_llm, seeded_skills

# Matches tests/graph_pipeline_fixtures.py's own TARGET_DURATION_MS -> 4 segments. Every API test
# that submits a job passes this explicitly rather than the 7-minute default, since a full-length
# run seeds far more LLM responses than these tests need.
API_TEST_TARGET_DURATION_MS = 100_000
API_TEST_SEGMENT_COUNT = 4

# Zero, for the identical reason tests/graph_pipeline_fixtures.py's FRAME_BUDGET is: every
# segment stays on Tier 0/1 deterministically and renders through real ffmpeg rather than
# dispatching to FakeRenderBackend's placeholder bytes.
FRAME_BUDGET = 0
FPS = 24


def fake_adapters(*, segment_count: int = API_TEST_SEGMENT_COUNT) -> Adapters:
    return Adapters(
        llm=seeded_llm(segment_count),
        tts=FakeTTSProvider(durations=[3000] * segment_count),
        storage=FakeStorage(),
        skills=seeded_skills(),
        queue=FakeJobQueue(),
        render=FakeRenderBackend(),
    )
