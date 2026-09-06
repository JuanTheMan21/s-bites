"""T38A: the session cookie, and what happens with no credentials at all.

Separate from ``tests/test_api_ownership.py`` because it is a separate question: that file asks
"can B see A's job", this one asks "how does a caller prove who they are". The cookie exists for
one concrete reason -- ``EventSource``, ``<video src>``, ``<img src>`` and ``<a href download>``
cannot set an ``Authorization`` header, and that is seven URLs in ``web/src/api/artifact-urls.ts``,
not just the SSE endpoint.
"""

from fastapi.testclient import TestClient

from api.auth import DEV_OWNER_ID, SESSION_COOKIE
from tests.api_fixtures import FPS, FRAME_BUDGET, authenticated_app, bearer, fake_adapters
from tests.test_api_ownership import OWNER_A

from api.app import create_app  # isort: skip -- grouped with the fixtures it is used beside


def test_no_credentials_at_all_is_rejected() -> None:
    app = authenticated_app()
    with TestClient(app) as client:
        assert client.get("/jobs").status_code == 401
        assert client.post("/jobs", json={"topic": "x"}).status_code == 401
        assert client.get("/auth/me").status_code == 401


def test_a_rejected_token_says_nothing_about_why() -> None:
    """The server logs the real reason; the client is told only that it failed. Otherwise a
    caller could probe which check it tripped, one request at a time."""
    app = authenticated_app()
    with TestClient(app) as client:
        # StubVerifier accepts anything, so the failure here is the missing scheme, not the token.
        response = client.get("/jobs", headers={"Authorization": OWNER_A})
        assert response.status_code == 401
        assert response.json()["detail"] == "no bearer token or session cookie"
        assert response.headers["WWW-Authenticate"] == "Bearer"


def test_the_session_cookie_authenticates_urls_that_cannot_send_a_header() -> None:
    app = authenticated_app()
    with TestClient(app, base_url="https://testserver") as client:
        opened = client.post("/auth/session", headers=bearer(OWNER_A))
        assert opened.status_code == 200
        assert opened.json()["owner_id"] == OWNER_A
        assert SESSION_COOKIE in client.cookies

        # No Authorization header from here on -- exactly what a <video> element can manage.
        assert client.get("/jobs").status_code == 200
        assert client.get("/auth/me").json()["owner_id"] == OWNER_A

        client.delete("/auth/session")
        assert client.get("/jobs").status_code == 401


def test_the_session_cookie_is_httponly_secure_and_samesite_none() -> None:
    """All three matter and none is incidental: ``HttpOnly`` keeps the token out of reach of any
    script on the page, and ``SameSite=None`` (which *requires* ``Secure``) is what lets the
    deployed frontend on one origin authenticate media served from another."""
    app = authenticated_app()
    with TestClient(app, base_url="https://testserver") as client:
        response = client.post("/auth/session", headers=bearer(OWNER_A))
    header = response.headers["set-cookie"].lower()
    assert "httponly" in header
    assert "secure" in header
    assert "samesite=none" in header


def test_the_session_route_refuses_the_cookie_it_issues() -> None:
    """A cookie must not be able to mint itself a fresh cookie -- that would let a cross-site
    request silently extend a session the user believes has lapsed."""
    app = authenticated_app()
    with TestClient(app, base_url="https://testserver") as client:
        client.post("/auth/session", headers=bearer(OWNER_A))
        assert client.post("/auth/session").status_code == 401


def test_auth_env_none_needs_no_credentials_at_all() -> None:
    """The local development and offline-test path: ``verifier=None``. Without it every existing
    API test, and ``cli.py``, would need a live Entra tenant to run."""
    app = create_app(fake_adapters(), frame_budget=FRAME_BUDGET, fps=FPS, run_worker=False)
    with TestClient(app) as client:
        assert client.get("/jobs").status_code == 200
        assert client.get("/auth/me").json()["owner_id"] == DEV_OWNER_ID


def test_state_changing_routes_refuse_the_cookie() -> None:
    """CSRF. The session cookie is SameSite=None because the deployed frontend and API are
    different origins, so the browser attaches it cross-site too. A JSON POST would at least need
    a CORS preflight an attacker's origin fails -- but `POST /jobs/{id}/resume` takes *no body*,
    so a plain cross-site HTML form would otherwise re-run a victim's job on their credit.

    Reads still accept the cookie; that is the whole point of having one.
    """
    app = authenticated_app()
    with TestClient(app, base_url="https://testserver") as client:
        client.post("/auth/session", headers=bearer(OWNER_A))
        assert client.get("/jobs").status_code == 200  # reads: cookie is fine

        assert client.post("/jobs", json={"topic": "x"}).status_code == 401
        assert client.post("/jobs/anything/resume").status_code == 401

        # And they still work with the header the real frontend always sends.
        assert (
            client.post(
                "/jobs", json={"topic": "x", "target_duration_ms": 100_000}, headers=bearer(OWNER_A)
            ).status_code
            == 201
        )
