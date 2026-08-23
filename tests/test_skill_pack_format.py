"""The pack file format, tested apart from the filesystem that stores it.

Split from ``test_disk_skill_registry.py`` because these are two responsibilities: this module
asks what a pack file *means*, that one asks which files exist. T11 reuses the format against
Blob without reusing any of the path handling, and the tests follow the same seam.
"""

import pytest

from adapters.skill_pack_format import (
    check_pack_name,
    check_version,
    parse_pack,
    split_frontmatter,
)

WITH_FRONTMATTER = """---
author: s_bites
updated: 2026-08-22
count: 3

notes: covers a: colon in the value
---

You are planning an explainer video.

Second paragraph.
"""

NO_FRONTMATTER = """You are planning an explainer video.

Second paragraph.
"""

RULE_NOT_AT_THE_TOP = """A heading

---

Body after a horizontal rule.
"""


def test_frontmatter_becomes_metadata_and_is_stripped_from_the_content() -> None:
    metadata, content = split_frontmatter(WITH_FRONTMATTER)

    assert metadata["author"] == "s_bites"
    assert content.startswith("You are planning")
    assert "---" not in content
    assert "author" not in content


def test_every_metadata_value_stays_a_string() -> None:
    """``dict[str, str]``, with no coercion anywhere -- the point of not using YAML.

    A date that arrives as a ``date`` and a count that arrives as an ``int`` are the start of a
    format that can express structure, and structure is the road back to executable content.
    """
    metadata, _ = split_frontmatter(WITH_FRONTMATTER)

    assert metadata["updated"] == "2026-08-22"
    assert metadata["count"] == "3"
    assert all(isinstance(value, str) for value in metadata.values())


def test_only_the_first_colon_splits_a_field() -> None:
    metadata, _ = split_frontmatter(WITH_FRONTMATTER)

    assert metadata["notes"] == "covers a: colon in the value"


def test_blank_lines_inside_the_frontmatter_are_ignored() -> None:
    assert len(split_frontmatter(WITH_FRONTMATTER)[0]) == 4


def test_a_pack_without_frontmatter_is_all_content() -> None:
    metadata, content = split_frontmatter(NO_FRONTMATTER)

    assert metadata == {}
    assert content == NO_FRONTMATTER.strip()


def test_a_horizontal_rule_below_the_first_line_is_content() -> None:
    """Frontmatter opens only on line one, so an ordinary markdown rule cannot hijack a file."""
    metadata, content = split_frontmatter(RULE_NOT_AT_THE_TOP)

    assert metadata == {}
    assert "---" in content


def test_an_empty_pack_is_empty_rather_than_an_error() -> None:
    assert split_frontmatter("") == ({}, "")


def test_an_unterminated_fence_is_an_error() -> None:
    """Silently treating it as content would hide the metadata a caller expects to be there."""
    with pytest.raises(ValueError, match="never closed"):
        split_frontmatter("---\nauthor: s_bites\n\nbody with no closing fence\n")


@pytest.mark.parametrize("line", ["author s_bites", ": no key", "   "], ids=repr)
def test_a_frontmatter_line_that_is_not_a_field_is_an_error(line: str) -> None:
    text = f"---\n{line}\n---\n\nbody\n"

    if not line.strip():  # a blank line is skipped, not rejected
        assert split_frontmatter(text) == ({}, "body")
        return

    with pytest.raises(ValueError, match="not 'key: value'"):
        split_frontmatter(text)


def test_identity_comes_from_the_path_not_from_the_file() -> None:
    """A pack cannot rename or re-version itself by editing its own frontmatter.

    Otherwise "where it is" and "what it claims to be" can disagree, and the registry would be
    handing back a pack whose name is not the name it was asked for.
    """
    pack = parse_pack("outline", "1.0", "---\nname: something-else\nversion: 9.9\n---\n\nbody\n")

    assert (pack.name, pack.version) == ("outline", "1.0")
    assert pack.metadata == {"name": "something-else", "version": "9.9"}
    assert pack.content == "body"


# --- Addressing rules ---------------------------------------------------------------------

REJECTED = [
    "",
    " ",
    "outline ",
    " outline",
    ".",
    "..",
    "../secrets",
    ".hidden",
    "a/b",
    "a\\b",
    "C:secrets",
    "a\0b",
    # Caught in review. Windows resolves a trailing dot away when it checks whether a path
    # exists but not when it enumerates it, so these either alias one pack to another or raise
    # a raw FileNotFoundError out of the listing. Neither is a thing a name should be able to do.
    "outline.",
    "outline..",
    "outline ..",
]


@pytest.mark.parametrize("check", [check_pack_name, check_version], ids=lambda c: c.__name__)
@pytest.mark.parametrize("value", REJECTED, ids=repr)
def test_a_malformed_name_or_version_is_rejected(check, value: str) -> None:
    """Parametrised over *both* checks on purpose.

    T6's standing lesson: ``FakeStorage.exists`` skipped ``check_key`` precisely because the
    test only covered one method. A rule verified on one caller of two is verified on neither.
    """
    with pytest.raises(ValueError):
        check(value)


@pytest.mark.parametrize("name", ["outline", "scene-authoring", "house_style", "a"], ids=repr)
def test_ordinary_pack_names_are_accepted(name: str) -> None:
    assert check_pack_name(name) == name


@pytest.mark.parametrize("version", ["1.0", "2.10", "draft", "2026-08-22"], ids=repr)
def test_ordinary_versions_are_accepted(version: str) -> None:
    assert check_version(version) == version
