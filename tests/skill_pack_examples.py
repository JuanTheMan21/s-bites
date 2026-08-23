"""Shared builders for skill-pack tests, mirroring ``segment_examples`` and ``slot_examples``.

One definition of "a registry holding these packs", used by the lookup tests, the failure tests
and the parity tests. Three copies of this would drift, and the drift would be invisible: each
file would still pass while testing a slightly different registry from the others.
"""

from pathlib import Path

from adapters.local.skill_registry import DiskSkillRegistry

# Deliberately out of order, and mixing numeric with named. Version ordering is D41's open
# question, so the default fixture is one that would expose a string sort rather than hide it.
MIXED_VERSIONS = {"outline": ["2.9", "1.0", "2.10", "draft"], "scripting": ["1.0"]}

# Newest first: numeric versions compare component-wise, so 2.10 beats 2.9, and a named version
# sorts below every numeric one because it is not a claim to be newest.
NEWEST_FIRST = ["2.10", "2.9", "1.0", "draft"]


def pack_text(name: str, version: str) -> str:
    """The on-disk form of one pack, with frontmatter, matching what ships in runtime_skills."""
    return f"---\nnotes: {name} v{version}\n---\n\n{name} prompt v{version}\n"


def write_packs(root: Path, packs: dict[str, list[str]]) -> Path:
    """Write ``{pack name: [versions]}`` under ``root`` and return it."""
    for name, versions in packs.items():
        directory = root / name
        directory.mkdir(parents=True, exist_ok=True)
        for version in versions:
            (directory / f"{version}.md").write_text(pack_text(name, version), encoding="utf-8")
    return root


def a_registry(root: Path, packs: dict[str, list[str]]) -> DiskSkillRegistry:
    """A ``DiskSkillRegistry`` rooted at ``root``, holding ``{pack name: [versions]}``."""
    return DiskSkillRegistry(write_packs(root, packs))
