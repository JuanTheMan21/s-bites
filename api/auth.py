"""Who is calling (T38A): the ``Principal`` dependency every job-scoped route takes, and the
session-cookie routes that make browser-native URLs work at all.

**Why a cookie exists alongside bearer tokens.** ``EventSource``, ``<video src>``, ``<img src>``
and ``<a href download>`` physically cannot send an ``Authorization`` header -- that is seven URLs
(``web/src/api/artifact-urls.ts``), not just the SSE endpoint the task text mentions. So:

- REST/JSON keeps ``Authorization: Bearer``, attached by ``openapi-fetch`` middleware. Every
  **state-changing** route demands it (``mutating_principal`` below) and will not accept the
  cookie, which is what keeps a ``SameSite=None`` cookie from becoming a CSRF hole.
- The browser-native GETs use an ``HttpOnly; Secure; SameSite=None`` cookie holding the very same
  JWT. No server-side session store -- consistent with D173's "no new data store to keep
  consistent"; the token is already self-contained and self-expiring.

``SameSite=None`` requires ``Secure``, and Chrome and Firefox both accept ``Secure`` cookies on
``http://localhost``, so the local two-user verification works without TLS. Do not be tempted to
drop ``Secure`` to "fix" local development.

**``AUTH_ENV=none``** hands back a fixed development principal. It is not a convenience: without
it ``cli.py``, local iteration and the whole offline test suite would need a live Entra tenant.
Same idiom as ``QUEUE_ENV``/``EVENTS_ENV``/``RENDER_ENV``.
"""

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from api.token_verifier import EntraTokenVerifier, TokenInvalid, owner_id_from_claims

logger = logging.getLogger(__name__)

SESSION_COOKIE = "s_bites_session"

# The development identity used when AUTH_ENV=none. A valid storage key segment (Storage rejects
# backslashes, absolute paths and ".."), and deliberately not GUID-shaped, so a dev-mode artifact
# tree is never mistaken for a real user's.
DEV_OWNER_ID = "dev.local"

router = APIRouter()


class Principal(BaseModel):
    """The authenticated caller. ``owner_id`` is the only field anything downstream depends on."""

    owner_id: str
    name: str | None = None
    username: str | None = None


DEV_PRINCIPAL = Principal(owner_id=DEV_OWNER_ID, name="Local Development", username="dev@local")


class Authenticator:
    """Turns a request into a ``Principal``. ``verifier is None`` means ``AUTH_ENV=none``."""

    def __init__(self, verifier: EntraTokenVerifier | None) -> None:
        self._verifier = verifier

    @property
    def enabled(self) -> bool:
        return self._verifier is not None

    async def aclose(self) -> None:
        if self._verifier is not None:
            await self._verifier.aclose()

    async def principal(self, request: Request, *, bearer_only: bool = False) -> Principal:
        if self._verifier is None:
            return DEV_PRINCIPAL
        token = _bearer_token(request)
        if token is None and not bearer_only:
            token = request.cookies.get(SESSION_COOKIE)
        if not token:
            raise _unauthorized("no bearer token or session cookie")
        try:
            claims = await self._verifier.verify(token)
        except TokenInvalid as exc:
            # Logged with the real reason, answered with a flat 401 -- a caller must not be able to
            # probe which check it failed.
            logger.info("rejected token: %s", exc)
            raise _unauthorized("invalid token") from None
        return _principal_from(claims)


async def current_principal(request: Request) -> Principal:
    """For **reads**. Accepts a bearer token or the session cookie, because the browser-native
    URLs among them can only ever supply the cookie."""
    return await _authenticator(request).principal(request)


async def mutating_principal(request: Request) -> Principal:
    """For **writes**, and the reason is CSRF.

    The session cookie is ``SameSite=None`` (it has to be -- the deployed frontend and API are
    different origins), so the browser attaches it to cross-site requests too. A JSON body would
    force a CORS preflight that an attacker's origin fails, but ``POST /jobs/{id}/resume`` takes
    *no body at all*: a plain cross-site HTML form could trigger it with the victim's cookie
    riding along, re-running their job and spending their credit.

    Requiring the bearer header on every state-changing route closes that outright, and costs
    nothing -- those routes are only ever called through ``openapi-fetch``, which sets the header.
    Only the header-less GETs (video, subtitles, SCORM, SSE) rely on the cookie, and a GET that
    changes nothing is not a CSRF target.
    """
    return await _authenticator(request).principal(request, bearer_only=True)


CurrentPrincipal = Annotated[Principal, Depends(current_principal)]
MutatingPrincipal = Annotated[Principal, Depends(mutating_principal)]


@router.get("/auth/me", response_model=Principal)
async def whoami(principal: CurrentPrincipal) -> Principal:
    """Who the caller is, as this API sees them. The frontend uses it to confirm the session
    cookie actually took, which is otherwise invisible to it (the cookie is ``HttpOnly``)."""
    return principal


@router.post("/auth/session", response_model=Principal)
async def create_session(request: Request, response: Response) -> Principal:
    """Exchange a bearer token for the session cookie the browser-native URLs need.

    ``bearer_only=True``: this is the one route that must never accept the cookie it issues.
    Otherwise a cross-site request could silently refresh a session the user believes has lapsed.
    """
    auth = _authenticator(request)
    principal = await auth.principal(request, bearer_only=True)
    if auth.enabled:
        token = _bearer_token(request)
        assert token is not None  # principal() above raises 401 when it is not
        response.set_cookie(
            SESSION_COOKIE,
            token,
            httponly=True,
            secure=True,
            samesite="none",
            max_age=_SESSION_MAX_AGE_S,
        )
    return principal


@router.delete("/auth/session", status_code=204)
async def end_session(response: Response) -> None:
    # Cleared with the same attributes it was set with -- a mismatched SameSite/Secure pair leaves
    # the original cookie in place in Chrome, so signing out would silently not.
    response.delete_cookie(SESSION_COOKIE, httponly=True, secure=True, samesite="none")


# Deliberately shorter than an Entra access token's own hour: the cookie is a bearer credential
# sitting in a browser, and MSAL can mint a fresh token silently whenever the frontend needs one.
_SESSION_MAX_AGE_S = 1800


def _authenticator(request: Request) -> Authenticator:
    return request.app.state.authenticator


def _bearer_token(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def _principal_from(claims: dict[str, Any]) -> Principal:
    return Principal(
        owner_id=owner_id_from_claims(claims),
        name=claims.get("name"),
        # `preferred_username` is the human-readable sign-in name; it is *not* a stable identifier
        # and must never be used as one -- that is owner_id's job.
        username=claims.get("preferred_username"),
    )


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(401, detail, headers={"WWW-Authenticate": "Bearer"})
