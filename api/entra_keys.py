"""Microsoft's published signing keys, fetched and cached (T38A).

Split out of ``api/token_verifier.py`` at the 200-line ceiling, and it is a genuinely separate
responsibility: this module knows about HTTP, caching and key rotation and nothing about claims;
``token_verifier.py`` knows about claims and nothing about how a key arrived.

The one non-obvious thing here is that each key carries **its own ``issuer``**, which is not part
of the JWK standard -- Microsoft adds it, and it is what makes the tenant-independent
(``common``) endpoint safe to validate against. A key is dropped rather than trusted if it lacks
one, since without it step 3 of the verifier's algorithm cannot be performed at all.
"""

import time
from dataclasses import dataclass
from typing import Any

import httpx
import jwt

JWKS_URL = "https://login.microsoftonline.com/{tenant}/discovery/v2.0/keys"

# Signing keys rotate (Microsoft's own "signing key rollover" doc), so the document is cached with
# a TTL and re-fetched when a token arrives bearing an unknown `kid` -- but no more often than
# MIN_REFETCH_S, so a stream of garbage tokens carrying invented kids cannot be turned into a
# request flood against Microsoft's endpoint.
JWKS_TTL_S = 3600
MIN_REFETCH_S = 300


class SigningKeyUnavailable(Exception):
    """No usable key for this token -- unknown ``kid``, or the document could not be fetched."""


@dataclass(frozen=True)
class SigningKey:
    """One published key, with the issuer Microsoft scoped it to.

    ``issuer`` is either the template ``https://login.microsoftonline.com/{tenantid}/v2.0`` (usable
    for any tenant, once the token's own ``tid`` is substituted in) or a literal issuer naming one
    specific tenant -- personal Microsoft accounts sign under
    ``9188040d-6c67-4c5b-b112-36a304b66dad`` -- which must then match exactly.
    """

    key: Any
    issuer: str


class JwksCache:
    """The tenant's signing-key document, kept fresh. One instance per verifier."""

    def __init__(self, tenant_id: str, client: httpx.AsyncClient | None = None) -> None:
        self._tenant_id = tenant_id
        self._client = client or httpx.AsyncClient(timeout=10.0)
        self._keys: dict[str, SigningKey] = {}
        self._fetched_at = 0.0

    async def aclose(self) -> None:
        await self._client.aclose()

    async def key_for(self, kid: str) -> SigningKey:
        now = time.monotonic()
        stale = now - self._fetched_at > JWKS_TTL_S
        unknown = kid not in self._keys
        if stale or (unknown and now - self._fetched_at > MIN_REFETCH_S):
            await self.refresh()
        key = self._keys.get(kid)
        if key is None:
            raise SigningKeyUnavailable(f"no signing key published for kid {kid!r}")
        return key

    async def refresh(self) -> None:
        url = JWKS_URL.format(tenant=self._tenant_id)
        try:
            response = await self._client.get(url)
            response.raise_for_status()
            document = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise SigningKeyUnavailable(f"could not fetch signing keys from {url}: {exc}") from exc

        keys: dict[str, SigningKey] = {}
        for entry in document.get("keys", []):
            kid = entry.get("kid")
            if not kid or not entry.get("issuer"):
                continue
            try:
                keys[kid] = SigningKey(key=jwt.PyJWK(entry).key, issuer=entry["issuer"])
            except jwt.PyJWTError:
                # One malformed key must not cost us the other, valid ones in the same document.
                continue
        if not keys:
            raise SigningKeyUnavailable(f"signing key document at {url} had no usable keys")
        self._keys = keys
        self._fetched_at = time.monotonic()
