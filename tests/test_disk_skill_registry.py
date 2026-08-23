"""What ``DiskSkillRegistry`` finds: lookup, ordering, and the shape of a loaded pack.

What it *refuses* -- malformed names, unreadable files -- is ``test_disk_registry_failures.py``.
Split at that seam when this file hit the 200-line ceiling: finding a pack and rejecting a
request are two jobs, and the second is the one T11's Blob registry has to copy exactly.

Always against ``tmp_path``, never ``runtime_skills/``. ``tests/test_runtime_skills.py`` is what
asserts the shipped packs, and a behavioural test that read them would start failing the day
someone adds a version.
"""

from pathlib import Path

import pytest

from adapters.local.skill_registry import DEFAULT_SKILLS_ROOT, DiskSkillRegistry
from interfaces import SkillPackNotFound, SkillRegistry
from tests.skill_pack_examples import a_registry


def test_the_default_root_is_the_runtime_skills_directory() -> None:
    """Named as a constant so ``config.py`` at T13 overrides it rather than rediscovering it."""
    assert Path("runtime_skills") == DEFAULT_SKILLS_ROOT
    assert isinstance(DiskSkillRegistry(), SkillRegistry)


async def test_loading_without_a_version_gets_the_newest(tmp_path: Path) -> None:
    """The D41 rule, on the real registry: 2.10 is newer than 2.9, which a string sort denies."""
    registry = a_registry(tmp_path, {"outline": ["2.9", "1.0", "2.10"]})

    assert (await registry.load("outline")).version == "2.10"
    assert (await registry.load("outline", "1.0")).version == "1.0"
    assert await registry.versions("outline") == ["2.10", "2.9", "1.0"]


async def test_a_named_version_sorts_below_every_numeric_one(tmp_path: Path) -> None:
    registry = a_registry(tmp_path, {"outline": ["1.0", "draft"]})

    assert await registry.versions("outline") == ["1.0", "draft"]
    assert (await registry.load("outline")).version == "1.0"


async def test_the_directory_and_the_stem_become_the_name_and_version(tmp_path: Path) -> None:
    registry = a_registry(tmp_path, {"scene-authoring": ["1.0"]})
    pack = await registry.load("scene-authoring")

    assert (pack.name, pack.version) == ("scene-authoring", "1.0")
    assert pack.content == "scene-authoring prompt v1.0"
    assert pack.metadata == {"notes": "scene-authoring v1.0"}


async def test_an_unknown_pack_raises_on_load_but_returns_empty_from_versions(
    tmp_path: Path,
) -> None:
    """Asymmetric on purpose, and identically to the fake: versions() is asked *before*."""
    registry = a_registry(tmp_path, {"outline": ["1.0"]})

    assert await registry.versions("nope") == []

    with pytest.raises(SkillPackNotFound, match="nope"):
        await registry.load("nope")


async def test_a_known_pack_at_an_unknown_version_also_raises(tmp_path: Path) -> None:
    registry = a_registry(tmp_path, {"outline": ["1.0"]})

    with pytest.raises(SkillPackNotFound, match=r"no version '9\.9'"):
        await registry.load("outline", "9.9")


async def test_list_packs_is_sorted_and_covers_only_directories(tmp_path: Path) -> None:
    registry = a_registry(tmp_path, {"scripting": ["1.0"], "outline": ["1.0"]})
    (tmp_path / "README.md").write_text("not a pack", encoding="utf-8")

    assert await registry.list_packs() == ["outline", "scripting"]


async def test_an_absent_root_is_an_empty_registry_rather_than_an_error(tmp_path: Path) -> None:
    """A checkout with no packs yet is a legitimate state, and list_packs is how you find out."""
    registry = DiskSkillRegistry(tmp_path / "does-not-exist")

    assert await registry.list_packs() == []
    assert await registry.versions("outline") == []

    with pytest.raises(SkillPackNotFound):
        await registry.load("outline")


async def test_a_pack_directory_with_no_versions_is_unknown(tmp_path: Path) -> None:
    (tmp_path / "outline").mkdir()
    registry = DiskSkillRegistry(tmp_path)

    assert await registry.versions("outline") == []
    with pytest.raises(SkillPackNotFound):
        await registry.load("outline")


async def test_non_markdown_files_are_not_versions(tmp_path: Path) -> None:
    registry = a_registry(tmp_path, {"outline": ["1.0"]})
    (tmp_path / "outline" / "notes.txt").write_text("scratch", encoding="utf-8")

    assert await registry.versions("outline") == ["1.0"]
