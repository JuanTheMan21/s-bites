"""Shared setup for the API test suite (T23): a fully fake ``Adapters`` bundle wired into a real
FastAPI app, so the app under test is exactly what production runs -- only the seven interfaces
underneath differ.
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.app import create_app
from config import Adapters
from tests.fakes import (
    FakeEventChannel,
    FakeJobQueue,
    FakeRenderBackend,
    FakeStorage,
    FakeTTSProvider,
)
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
        events=FakeEventChannel(),
    )


class StubVerifier:
    """Stands in for ``EntraTokenVerifier`` in tests about what happens *after* a token is known
    to be good -- ownership, sessions, 401s. The token string simply *is* the owner id, so a test
    can sign in as anyone without a tenant, a network call, or a signing key.

    The real verifier's own algorithm is tested against locally-minted RSA tokens in
    ``tests/test_token_verifier.py``; mixing the two concerns would make both harder to read.
    """

    async def verify(self, token: str) -> dict[str, str]:
        tid, _, oid = token.partition(".")
        return {"tid": tid, "oid": oid, "name": token, "preferred_username": f"{token}@example"}

    async def aclose(self) -> None:
        return None


def authenticated_app() -> FastAPI:
    """An app with authentication switched on, backed by ``StubVerifier``."""
    return create_app(
        fake_adapters(),
        frame_budget=FRAME_BUDGET,
        fps=FPS,
        run_worker=False,
        verifier=StubVerifier(),
    )


def bearer(owner_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {owner_id}"}


def https_client(app: FastAPI) -> TestClient:
    """The session cookie is ``Secure``, deliberately and permanently -- ``SameSite=None``
    requires it. A cookie jar will not send a Secure cookie over plain http, so any test that
    exercises the cookie has to speak https, exactly as a real browser does."""
    return TestClient(app, base_url="https://testserver")
