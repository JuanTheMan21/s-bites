"""T38A: the Entra token validation algorithm, against real RS256 signatures.

One test per step of the algorithm in ``api/token_verifier.py``'s docstring. The steps that only
exist in the tenant-independent (``common``) form -- the signing-key issuer check and the
``tid``/``iss`` consistency check -- get the most attention, because they are the ones a
single-tenant implementation would not have and therefore the ones most likely to be "simplified"
away by someone later who has only ever seen the single-tenant shape.
"""

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from api.token_verifier import ISSUER_TEMPLATE, TokenInvalid, owner_id_from_claims
from tests.entra_fixtures import (
    MSA_TENANT,
    OID,
    TENANT_A,
    TENANT_B,
    jwks_document,
    mint,
    verifier,
)


async def test_a_good_token_validates_and_yields_an_owner_id() -> None:
    claims = await verifier().verify(mint())
    assert claims["tid"] == TENANT_A
    assert owner_id_from_claims(claims) == f"{TENANT_A}.{OID}"


def test_owner_id_joins_tenant_and_object_id_with_a_dot() -> None:
    """Both halves are required: `oid` is only unique *within* a tenant, so two users in different
    tenants can share one. The separator is a dot and not a colon because a colon is an illegal
    Windows filename character, which would break DiskStorage on a dev machine only -- the cloud
    path would look fine, which is the worst way for this to go wrong.
    """
    owner = owner_id_from_claims({"tid": TENANT_A, "oid": OID})
    assert owner == f"{TENANT_A}.{OID}"
    assert ":" not in owner


async def test_a_token_for_another_audience_is_rejected() -> None:
    with pytest.raises(TokenInvalid):
        await verifier().verify(mint(aud="some-other-app"))


async def test_an_expired_token_is_rejected() -> None:
    with pytest.raises(TokenInvalid):
        await verifier().verify(mint(expires_in_s=-60))


async def test_a_token_signed_by_the_wrong_key_is_rejected() -> None:
    stranger = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with pytest.raises(TokenInvalid):
        await verifier().verify(mint(key=stranger))


async def test_an_unknown_kid_is_rejected() -> None:
    with pytest.raises(TokenInvalid):
        await verifier().verify(mint(kid="a-kid-nobody-published"))


async def test_the_algorithm_is_pinned_rather_than_read_from_the_header() -> None:
    """Honouring the token's own ``alg`` is how ``alg: none`` and HMAC-confusion attacks work."""
    forged = mint(algorithm="HS256", key="x" * 32)
    with pytest.raises(TokenInvalid):
        await verifier().verify(forged)


async def test_iss_must_correspond_to_tid() -> None:
    """Step 6. A token whose ``iss`` names one tenant while ``tid`` claims another is exactly the
    cross-tenant confusion the tenant-independent metadata exists to prevent."""
    mismatched = mint(tid=TENANT_A, iss=ISSUER_TEMPLATE.replace("{tenantid}", TENANT_B))
    with pytest.raises(TokenInvalid):
        await verifier().verify(mismatched)


async def test_a_non_guid_tid_is_rejected() -> None:
    with pytest.raises(TokenInvalid):
        await verifier().verify(mint(tid="not-a-guid", iss="https://login.microsoftonline.com/x"))


async def test_allowed_tenants_is_the_enterprise_lock() -> None:
    """Empty accepts any tenant -- the demo/personal-tenant setting. Populated, it is an ordinary
    single-tenant enterprise app: only that company's directory may sign in."""
    locked = verifier(allowed_tenants=frozenset({TENANT_A}))
    assert (await locked.verify(mint(tid=TENANT_A)))["tid"] == TENANT_A

    with pytest.raises(TokenInvalid):
        await verifier(allowed_tenants=frozenset({TENANT_A})).verify(mint(tid=TENANT_B))


async def test_a_key_with_a_literal_issuer_must_match_exactly() -> None:
    """Step 3's other branch. Personal-account keys are published with a literal issuer naming
    Microsoft's own consumer tenant, and must not be usable to validate a token claiming any other
    tenant -- substituting into them is precisely what must not happen."""
    literal = ISSUER_TEMPLATE.replace("{tenantid}", MSA_TENANT)
    consumer_keys = verifier(document=jwks_document(issuer=literal))

    assert (await consumer_keys.verify(mint(tid=MSA_TENANT)))["tid"] == MSA_TENANT

    with pytest.raises(TokenInvalid):
        await verifier(document=jwks_document(issuer=literal)).verify(mint(tid=TENANT_A))


async def test_a_key_published_without_an_issuer_is_never_used() -> None:
    """Without a per-key issuer, step 3 cannot be performed at all -- so the key is dropped rather
    than trusted against a guessed issuer."""
    document = jwks_document()
    del document["keys"][0]["issuer"]
    with pytest.raises(TokenInvalid):
        await verifier(document=document).verify(mint())


async def test_a_missing_scope_is_rejected() -> None:
    with pytest.raises(TokenInvalid):
        await verifier().verify(mint(scp="SomethingElse"))


async def test_the_required_app_role_gates_who_may_use_the_api() -> None:
    """The code half of "an AD group of people who can access the website". Off unless configured,
    since it needs app roles to be defined in the app registration first."""
    gated = verifier(required_app_role="Studio.User")
    assert (await gated.verify(mint(roles=["Studio.User"])))["oid"] == OID

    with pytest.raises(TokenInvalid):
        await verifier(required_app_role="Studio.User").verify(mint(roles=["Someone.Else"]))
    with pytest.raises(TokenInvalid):
        await verifier(required_app_role="Studio.User").verify(mint())


async def test_garbage_is_rejected_without_raising_anything_but_token_invalid() -> None:
    """Every failure path has to arrive as TokenInvalid, since that is the only exception
    ``api/auth.py`` translates into a 401 -- anything else becomes a 500 and, worse, reads as a
    server fault rather than a bad credential."""
    for garbage in ("", "not-a-jwt", "a.b.c", "Bearer something"):
        with pytest.raises(TokenInvalid):
            await verifier().verify(garbage)


async def test_the_keys_document_is_fetched_once_and_cached() -> None:
    """Re-fetching per request would put a network round trip in front of every API call."""
    shared = verifier()
    calls = 0
    original = shared._keys.refresh

    async def counting_refresh() -> None:
        nonlocal calls
        calls += 1
        await original()

    shared._keys.refresh = counting_refresh  # type: ignore[method-assign]
    await shared.verify(mint())
    await shared.verify(mint())
    assert calls == 1, "signing keys should be cached across requests"


async def test_an_unknown_kid_does_not_trigger_a_refetch_storm() -> None:
    """MIN_REFETCH_S: a stream of tokens carrying invented kids must not become a request flood
    against Microsoft's endpoint."""
    shared = verifier()
    await shared.verify(mint())
    calls = 0
    original = shared._keys.refresh

    async def counting_refresh() -> None:
        nonlocal calls
        calls += 1
        await original()

    shared._keys.refresh = counting_refresh  # type: ignore[method-assign]
    for _ in range(5):
        with pytest.raises(TokenInvalid):
            await shared.verify(mint(kid="invented"))
    assert calls == 0, "an unknown kid re-fetched inside the minimum interval"
