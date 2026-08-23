"""The on-disk format of a runtime skill pack, and the rules for addressing one.

Lives at the root of ``adapters/`` rather than under ``adapters/local/`` because the bytes are
the same wherever they are stored: T11's Blob-backed registry pulls the identical file out of a
container and has to read it the identical way. A shared module here beats an ``azure`` adapter
importing from ``local`` later.

**A pack is a markdown file whose stem is its version, in a directory whose name is the pack.**
An optional frontmatter block carries ``metadata``::

    ---
    author: s_bites
    updated: 2026-08-22
    ---

    You are planning an explainer video...

The frontmatter parser is deliberately smaller than YAML. It produces ``dict[str, str]`` and
cannot express anything else -- no nesting, no lists, no type coercion, no tags, and nothing that
constructs an object. That is the load-bearing half of T7's definition of done ("pack content is
data, not code") made structural rather than promised: a format that *cannot* carry code is a
stronger guarantee than a convention not to write any. Values stay strings, so ``updated`` above
is ``"2026-08-22"`` and never a date.
"""

from interfaces import SkillPack

PACK_SUFFIX = ".md"
FENCE = "---"

# A name becomes a path segment on disk and a blob-name prefix on Azure. These are the characters
# that would let it mean something other than one segment in either place.
UNSAFE_CHARACTERS = ("/", "\\", ":", "\0")


def check_pack_name(name: str) -> str:
    """Return ``name`` if it is a usable pack name; raise ``ValueError`` if not.

    Malformed is not the same as absent (D39). ``versions`` returns an empty list for a pack
    that does not exist, but ``../../secrets`` is not a pack that does not exist -- it is a
    request to read outside the registry, and answering it with an empty list would make a
    traversal attempt look like an ordinary miss.
    """
    return _check_segment(name, "pack name")


def check_version(version: str) -> str:
    """Return ``version`` if it is a usable version string; raise ``ValueError`` if not.

    Same rules as a pack name: a version is the other half of the path, so a caller who can put
    a separator in it can escape the root just as easily.
    """
    return _check_segment(version, "version")


def parse_pack(name: str, version: str, text: str) -> SkillPack:
    """Build a ``SkillPack`` from a pack file's text.

    ``name`` and ``version`` come from the storage layer -- the directory and the file stem on
    disk -- rather than from the file's own contents. A pack cannot rename or re-version itself
    by editing its frontmatter, which keeps "where it is" and "what it claims to be" from
    disagreeing.

    Raises:
        ValueError: the frontmatter is opened and not closed, or holds a line that is not
            ``key: value``.
    """
    metadata, content = split_frontmatter(text)
    return SkillPack(name=name, version=version, content=content, metadata=metadata)


def split_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Split ``text`` into its metadata fields and its content.

    Frontmatter exists only when the **first** line is exactly ``---``. A pack that wants to open
    with a markdown horizontal rule puts a blank line above it; anything else would make an
    ordinary rule near the top of a file change how the whole file parses.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != FENCE:
        return {}, text.strip()

    close = next((i for i, line in enumerate(lines[1:], 1) if line.strip() == FENCE), None)
    if close is None:
        raise ValueError(f"frontmatter opened with {FENCE!r} but is never closed")

    return _parse_fields(lines[1:close]), "\n".join(lines[close + 1 :]).strip()


def _parse_fields(lines: list[str]) -> dict[str, str]:
    """Flat ``key: value`` pairs, values kept verbatim as strings. Blank lines are ignored."""
    fields: dict[str, str] = {}
    for line in lines:
        if not line.strip():
            continue
        key, separator, value = line.partition(":")
        if not separator or not key.strip():
            raise ValueError(f"frontmatter line is not 'key: value': {line!r}")
        fields[key.strip()] = value.strip()
    return fields


# The trailing-dot rule is the one here that looks like tidiness and is not, so it is written
# down before someone simplifies it away. Windows strips trailing dots when it resolves a path
# for `stat`, but *not* when it enumerates a directory. So on this project's primary platform
# `outline.` passes an existence check against the `outline` directory -- aliasing one pack to
# another under a name that is not its own -- while `outline..` passes the same check and then
# raises a raw `FileNotFoundError` out of the listing, straight through the adapter boundary.
def _check_segment(value: str, label: str) -> str:
    if not value or value != value.strip():
        raise ValueError(f"{label} must be non-empty and unpadded, got {value!r}")
    if value.startswith(".") or value.endswith("."):
        raise ValueError(f"{label} must not start or end with '.', got {value!r}")
    if any(character in value for character in UNSAFE_CHARACTERS):
        raise ValueError(f"{label} must be a single path segment, got {value!r}")
    return value
