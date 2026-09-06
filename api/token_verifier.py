"""Microsoft Entra ID access-token verification (T38A).

Pure verification: no FastAPI, no request objects, no cookies. ``api/auth.py`` owns the HTTP side
and calls into this; ``api/entra_keys.py`` owns fetching the signing keys. Split that way for the
200-line ceiling and because the algorithm below is worth testing against locally-minted JWTs with
no app around it.

**The tenancy of this API is a configuration value, not a code path.** ``tenant_id="common"``
accepts any Microsoft identity (what this project's own personal-MSA tenant can actually do);
``tenant_id="<guid>"`` with ``allowed_tenants={"<guid>"}`` is an ordinary single-tenant enterprise
app. Verification is identical either way, because Microsoft's tenant-independent validation is a
strict *superset* of the single-tenant one -- it does everything single-tenant does plus steps 3
and 6 below. Building the general form and pinning it with config is the documented way to write
this, not a shortcut around single-tenant.

Steps 2-9 follow *Access tokens in the Microsoft identity platform -> Validate tokens* verbatim
(step 1, fetching the keys, is ``api/entra_keys.py``). **Every step is load-bearing; do not
"simplify" one away.** Step 3 in particular is what ties tenant -> issuer -> signing key into a
chain of trust: without it, a token from any tenant would validate against a key scoped to another.
"""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

import httpx
import jwt

from api.entra_keys import JwksCache, SigningKey, SigningKeyUnavailable

ISSUER_TEMPLATE = "https://login.microsoftonline.com/{tenantid}/v2.0"


class TokenInvalid(Exception):
    """A token that must not be honoured. The message says why, for logs -- never for the client:
    ``api/auth.py`` returns a flat 401 so a caller cannot probe which check it failed."""


@dataclass(frozen=True)
class EntraConfig:
    """Everything about *which* identities this API accepts. Read from the environment in
    ``api/main.py`` (the only module in ``api/`` permitted to) and passed down from there."""

    tenant_id: str
    client_id: str
    allowed_tenants: frozenset[str] = frozenset()
    required_scope: str = ""
    required_app_role: str = ""


class EntraTokenVerifier:
    """Validates a bearer token and returns its claims."""

    def __init__(self, config: EntraConfig, client: httpx.AsyncClient | None = None) -> None:
        self._config = config
        self._keys = JwksCache(config.tenant_id, client)

    async def aclose(self) -> None:
        await self._keys.aclose()

    async def verify(self, token: str) -> dict[str, Any]:
        """Return the validated claims, or raise ``TokenInvalid``."""
        header = self._header(token)
        # (2) Select the key by `kid`. RS256 is pinned rather than read from the header --
        # honouring the token's own `alg` is exactly how `alg: none` and HMAC-confusion work.
        if header.get("alg") != "RS256":
            raise TokenInvalid(f"unexpected signing algorithm {header.get('alg')!r}")
        kid = header.get("kid")
        if not kid:
            raise TokenInvalid("token header carries no kid")
        try:
            signing_key = await self._keys.key_for(kid)
        except SigningKeyUnavailable as exc:
            raise TokenInvalid(str(exc)) from exc

        # The unverified `tid` is used *only* to build the issuer string that the real,
        # signature-checked decode below then enforces -- and step (6) re-checks the verified
        # `tid` against it afterwards, so a forged `tid` cannot survive the round trip.
        claimed_tid = self._unverified_tid(token)
        expected_issuer = self._expected_issuer(signing_key, claimed_tid)

        # (4)(5) Signature, exp, nbf, plus aud and iss, all inside PyJWT.
        try:
            claims = jwt.decode(
                token,
                key=signing_key.key,
                algorithms=["RS256"],
                audience=self._config.client_id,
                issuer=expected_issuer,
                options={"require": ["exp", "iat", "iss", "aud", "sub"]},
            )
        except jwt.PyJWTError as exc:
            raise TokenInvalid(f"token rejected: {exc}") from exc

        self._check_tenant(claims, claimed_tid)
        self._check_scope(claims)
        self._check_app_role(claims)
        if not claims.get("oid"):
            raise TokenInvalid("token carries no oid claim")
        return claims

    def _header(self, token: str) -> dict[str, Any]:
        try:
            return jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise TokenInvalid(f"unparseable token header: {exc}") from exc

    def _unverified_tid(self, token: str) -> str:
        try:
            claims = jwt.decode(token, options={"verify_signature": False})
        except jwt.PyJWTError as exc:
            raise TokenInvalid(f"unparseable token body: {exc}") from exc
        tid = claims.get("tid")
        if not isinstance(tid, str) or not _is_guid(tid):
            raise TokenInvalid(f"tid is not a GUID: {tid!r}")
        return tid

    def _expected_issuer(self, signing_key: SigningKey, claimed_tid: str) -> str:
        """(3) Validate the signing key issuer: substitute into a templated one, demand an exact
        match against a literal one."""
        if "{tenantid}" not in signing_key.issuer:
            return signing_key.issuer
        return signing_key.issuer.replace("{tenantid}", claimed_tid)

    def _check_tenant(self, claims: dict[str, Any], claimed_tid: str) -> None:
        """(6)(7) `tid` is a GUID, `iss` is built from that exact `tid`, and -- the enterprise
        lock -- `tid` is one this deployment is configured to accept."""
        tid = claims.get("tid")
        if not isinstance(tid, str) or not _is_guid(tid):
            raise TokenInvalid(f"tid is not a GUID: {tid!r}")
        if tid != claimed_tid:
            raise TokenInvalid("verified tid does not match the tid used to resolve the issuer")
        if claims.get("iss") != ISSUER_TEMPLATE.replace("{tenantid}", tid):
            raise TokenInvalid("iss does not correspond to tid")
        allowed = self._config.allowed_tenants
        if allowed and tid not in allowed:
            raise TokenInvalid(f"tenant {tid} is not in ENTRA_ALLOWED_TENANTS")

    def _check_scope(self, claims: dict[str, Any]) -> None:
        """(8) `scp` is space-delimited in a v2.0 token."""
        required = self._config.required_scope
        if required and required not in str(claims.get("scp", "")).split():
            raise TokenInvalid(f"token is missing the {required!r} scope")

    def _check_app_role(self, claims: dict[str, Any]) -> None:
        """(9) The code half of "an AD group for who may use the website". The other half is *User
        assignment required* on the enterprise app, which Entra enforces before ever issuing a
        token. Off by default, since it needs app roles to actually be defined first."""
        required = self._config.required_app_role
        if not required:
            return
        roles = claims.get("roles") or []
        if not isinstance(roles, list) or required not in roles:
            raise TokenInvalid(f"token is missing the {required!r} app role")


def owner_id_from_claims(claims: dict[str, Any]) -> str:
    """The stable per-user key, and the prefix every one of that user's storage keys sits under.

    **Both halves are required.** Microsoft's docs are explicit that `sub`/`oid` are only meaningful
    *within* an issuer -- two users in different tenants can share an `oid` -- and that "the `tid`
    claim must be part of the key used to access the user's data."

    Joined with ``.``, never ``:``. A colon is a legal blob name but an illegal Windows filename
    character (the drive separator), which would break ``DiskStorage`` on the dev machine only --
    the worst kind of bug to introduce, since the cloud path would look fine.
    """
    return f"{claims['tid']}.{claims['oid']}"


def _is_guid(value: str) -> bool:
    try:
        UUID(value)
    except ValueError:
        return False
    return True
