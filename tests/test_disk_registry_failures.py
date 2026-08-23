"""What ``DiskSkillRegistry`` refuses, and how it reports a backend that misbehaved.

The other half of ``test_disk_skill_registry.py``. This is the half T11's Blob registry has to
match exactly: which requests are rejected before they reach the backend, and which exception a
caller sees when one fails. A registry that finds packs but disagrees with its counterpart about
errors is the parity bug that only shows up on the cloud path.
"""

from pathlib import Path

import pytest

from adapters.local.skill_registry import DiskSkillRegistry
from interfaces import ProviderUnavailable
from tests.skill_pack_examples import a_registry

# Names that mean something other than themselves once a filesystem sees them. The first group
# escapes the root; the trailing-dot group was found in review and is subtler -- Windows drops a
# trailing dot when it resolves a path for an existence check but not when it enumerates a
# directory, so "outline." silently resolves to the "outline" directory and "outline.." passes
# the existence check and then raises FileNotFoundError out of the listing.
MALFORMED_NAMES = [
    "..",
    "../..",
    "../other",
    "a/b",
    "a\\b",
    "",
    " ",
    "outline.",
    "outline..",
]


@pytest.mark.parametrize("method", ["load", "versions"])
@pytest.mark.parametrize("name", MALFORMED_NAMES, ids=repr)
async def test_a_malformed_pack_name_is_rejected_by_every_method(
    tmp_path: Path, method: str, name: str
) -> None:
    """Malformed is not absent (D39). Answering ``../secrets`` with ``[]`` reports a traversal
    attempt as an ordinary miss, and the caller cannot tell the difference.

    Parametrised across both name-taking methods -- ``list_packs`` takes none -- because T6's
    lesson was that a rule verified on one method of six is verified on none. That lesson is
    also why the trailing-dot entries are here: the first version of this list had none, and
    that is exactly the gap review found.
    """
    registry = a_registry(tmp_path, {"outline": ["1.0"]})

    with pytest.raises(ValueError):
        await getattr(registry, method)(name)


@pytest.mark.parametrize("version", MALFORMED_NAMES, ids=repr)
async def test_a_malformed_version_is_rejected(tmp_path: Path, version: str) -> None:
    registry = a_registry(tmp_path, {"outline": ["1.0"]})

    with pytest.raises(ValueError):
        await registry.load("outline", version)


async def test_a_pack_name_that_aliases_another_pack_is_rejected(tmp_path: Path) -> None:
    """The regression test for the review finding, stated as behaviour rather than as a rule.

    Before the fix, ``load("outline.")`` returned the contents of ``outline/1.0.md`` inside a
    ``SkillPack`` whose ``name`` was ``"outline."`` -- a pack whose identity did not match what
    it was loaded from, which is the one thing ``parse_pack`` promises cannot happen.
    """
    registry = a_registry(tmp_path, {"outline": ["1.0"]})

    assert (await registry.load("outline")).name == "outline"

    with pytest.raises(ValueError, match="must not start or end with"):
        await registry.load("outline.")


async def test_a_pack_outside_the_root_is_unreachable(tmp_path: Path) -> None:
    """The end-to-end statement of the rule, rather than the unit form above it."""
    (tmp_path / "secrets.md").write_text("do not read me", encoding="utf-8")
    registry = a_registry(tmp_path / "packs", {"outline": ["1.0"]})

    with pytest.raises(ValueError):
        await registry.load("../secrets")


# --- Failure translation --------------------------------------------------------------------


async def test_an_unreadable_pack_file_is_an_adapter_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Disk is this adapter's backend, so a failed read is what Blob's failed request will be.

    Injected rather than staged on the filesystem: ``chmod`` does not deny reads this way on
    Windows, which is the primary platform here, so a permissions-based version of this test
    would pass by not failing.
    """
    registry = a_registry(tmp_path, {"outline": ["1.0"]})

    def refuse(*args: object, **kwargs: object) -> str:
        raise OSError("device is busy")

    monkeypatch.setattr(Path, "read_text", refuse)

    with pytest.raises(ProviderUnavailable, match="could not read"):
        await registry.load("outline")


async def test_a_directory_that_cannot_be_listed_is_an_adapter_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No raw OS exception may escape ``versions``, whatever the cause.

    ``glob`` is a generator, so an ``OSError`` surfaces when the first entry is pulled rather
    than at the call -- subtle enough that it escaped once already, as the trailing-dot finding.
    An unreadable directory is the backend failing rather than a pack being absent, so it
    translates instead of quietly returning an empty list and looking like a miss.
    """
    registry = a_registry(tmp_path, {"outline": ["1.0"]})

    def refuse(*args: object, **kwargs: object) -> list[Path]:
        raise OSError("permission denied")

    monkeypatch.setattr(Path, "glob", refuse)

    with pytest.raises(ProviderUnavailable, match="could not list"):
        await registry.versions("outline")


async def test_a_pack_that_is_not_utf8_is_a_value_error_not_an_adapter_error(
    tmp_path: Path,
) -> None:
    """The backend answered; the data is malformed. That is ours, not the backend's."""
    (tmp_path / "outline").mkdir()
    (tmp_path / "outline" / "1.0.md").write_bytes(b"\xff\xfe not utf-8 at all")
    registry = DiskSkillRegistry(tmp_path)

    with pytest.raises(ValueError, match="not valid UTF-8"):
        await registry.load("outline")
