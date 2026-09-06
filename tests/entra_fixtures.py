"""Locally-minted Entra tokens and a fake signing-key endpoint (T38A).

Real RS256 signatures over a throwaway key pair, served through an ``httpx.MockTransport`` shaped
exactly like Microsoft's own keys document -- including the per-key ``issuer`` field, which is not
part of the JWK standard and is the thing step 3 of the verifier's algorithm depends on. A stub
that omitted it would let the verifier's most important check pass vacuously.
"""

import time
from typing import Any

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

from api.token_verifier import ISSUER_TEMPLATE, EntraConfig, EntraTokenVerifier

TENANT_A = "551f939c-8006-4967-8945-7f4b86b77f1a"
TENANT_B = "99999999-9999-9999-9999-999999999999"
# Microsoft's real, fixed tenant for personal accounts. Its keys carry a literal issuer rather
# than the template, which is a genuinely different branch in _expected_issuer.
MSA_TENANT = "9188040d-6c67-4c5b-b112-36a304b66dad"

CLIENT_ID = "aaaabbbb-0000-cccc-1111-dddd2222eeee"
OID = "cccccccc-cccc-cccc-cccc-cccccccccccc"
SCOPE = "Jobs.ReadWrite"
KID = "test-key-1"

_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def jwks_document(*, kid: str = KID, issuer: str | None = None) -> dict[str, Any]:
    """``issuer=None`` means the tenant-independent template, which is what the ``common``
    endpoint actually publishes."""
    jwk = jwt.algorithms.RSAAlgorithm.to_jwk(_PRIVATE_KEY.public_key(), as_dict=True)
    jwk.update({"kid": kid, "use": "sig", "alg": "RS256", "issuer": issuer or ISSUER_TEMPLATE})
    return {"keys": [jwk]}


def mint(
    *,
    tid: str = TENANT_A,
    aud: str = CLIENT_ID,
    oid: str = OID,
    scp: str = SCOPE,
    roles: list[str] | None = None,
    iss: str | None = None,
    expires_in_s: int = 3600,
    kid: str = KID,
    algorithm: str = "RS256",
    key: Any = None,
) -> str:
    now = int(time.time())
    claims: dict[str, Any] = {
        "iss": iss if iss is not None else ISSUER_TEMPLATE.replace("{tenantid}", tid),
        "aud": aud,
        "sub": "subject-abc",
        "tid": tid,
        "oid": oid,
        "iat": now,
        "nbf": now,
        "exp": now + expires_in_s,
        "name": "Test User",
        "preferred_username": "test@example.com",
    }
    if scp:
        claims["scp"] = scp
    if roles is not None:
        claims["roles"] = roles
    signing_key = key if key is not None else _PRIVATE_KEY
    return jwt.encode(claims, signing_key, algorithm=algorithm, headers={"kid": kid})


def verifier(
    *,
    document: dict[str, Any] | None = None,
    tenant_id: str = "common",
    allowed_tenants: frozenset[str] = frozenset(),
    required_scope: str = SCOPE,
    required_app_role: str = "",
) -> EntraTokenVerifier:
    doc = document if document is not None else jwks_document()
    transport = httpx.MockTransport(lambda _request: httpx.Response(200, json=doc))
    return EntraTokenVerifier(
        EntraConfig(
            tenant_id=tenant_id,
            client_id=CLIENT_ID,
            allowed_tenants=allowed_tenants,
            required_scope=required_scope,
            required_app_role=required_app_role,
        ),
        client=httpx.AsyncClient(transport=transport),
    )
