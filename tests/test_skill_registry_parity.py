"""The two ``SkillRegistry`` implementations, held to one set of assertions.

This file is what closes D41. The fake and the disk registry each sort a different data
structure -- a dict of tuples and a directory listing -- and until T7 they each defined their own
answer to "which version is newest". A string sort puts ``2.10`` below ``2.9``, so the two agreed
on every pack with one version and would have disagreed on the first pack with two. That is a
divergence nothing catches at the moment it is introduced.

Both now import ``interfaces.version_key``, and everything below runs against both. T11 adds a
Blob-backed registry and joins ``REGISTRIES`` -- at which point these become the parity tests the
``adapter-parity`` agent is checking for at T13, written before the second implementation existed
rather than after the bug did.
"""

from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from adapters.azure.skill_registry import BlobSkillRegistry
from interfaces import SkillPack, SkillPackNotFound, SkillRegistry
from tests.azure_live import CONNECTION_STRING, require, throwaway_container
from tests.fakes import FakeSkillRegistry
from tests.skill_pack_examples import MIXED_VERSIONS as PACKS
from tests.skill_pack_examples import NEWEST_FIRST, a_registry, pack_text


def build_fake() -> SkillRegistry:
    registry = FakeSkillRegistry()
    for name, versions in PACKS.items():
        for version in versions:
            registry.add(SkillPack(name=name, version=version, content=f"{name} prompt v{version}"))
    return registry


# T11 joined by adding one entry, and the assertions below did not change -- which is what T7 was
# buying when it put the pack format in `adapters/skill_pack_format.py` rather than inside the
# disk registry. `blob` is marked `live`, so the default run still covers the other two offline.
REGISTRIES = ["fake", "disk", pytest.param("blob", marks=pytest.mark.live)]


@pytest.fixture(params=REGISTRIES)
async def registry(request: pytest.FixtureRequest, tmp_path: Path) -> AsyncIterator[SkillRegistry]:
    """One registry per implementation, holding identical packs."""
    if request.param == "fake":
        yield build_fake()
        return
    if request.param == "disk":
        yield a_registry(tmp_path, PACKS)
        return

    blobs = {
        f"{name}/{version}.md": pack_text(name, version)
        for name, versions in PACKS.items()
        for version in versions
    }
    async with throwaway_container(blobs) as container:
        blob_registry = BlobSkillRegistry(require(CONNECTION_STRING), container)
        try:
            yield blob_registry
        finally:
            await blob_registry.aclose()


async def test_versions_are_newest_first(registry: SkillRegistry) -> None:
    """The assertion D41 exists for. It is the same list on both, or the rule is not shared."""
    assert await registry.versions("outline") == NEWEST_FIRST


async def test_no_version_means_the_newest_one(registry: SkillRegistry) -> None:
    assert (await registry.load("outline")).version == "2.10"


async def test_an_explicit_version_is_returned_exactly(registry: SkillRegistry) -> None:
    for version in PACKS["outline"]:
        assert (await registry.load("outline", version)).version == version


async def test_a_loaded_pack_carries_the_name_it_was_asked_for(registry: SkillRegistry) -> None:
    pack = await registry.load("scripting")

    assert (pack.name, pack.version) == ("scripting", "1.0")
    assert pack.content == "scripting prompt v1.0"


async def test_list_packs_is_sorted(registry: SkillRegistry) -> None:
    assert await registry.list_packs() == ["outline", "scripting"]


async def test_an_unknown_pack_returns_empty_from_versions(registry: SkillRegistry) -> None:
    """Never raises for an absent pack -- this is the question asked *before* committing."""
    assert await registry.versions("nope") == []


async def test_an_unknown_pack_raises_from_load(registry: SkillRegistry) -> None:
    with pytest.raises(SkillPackNotFound, match="nope"):
        await registry.load("nope")


async def test_a_known_pack_at_an_unknown_version_raises(registry: SkillRegistry) -> None:
    """Same exception *and* the same message shape, so a caller can match on either."""
    with pytest.raises(SkillPackNotFound, match=r"no version '9\.9'"):
        await registry.load("outline", "9.9")
