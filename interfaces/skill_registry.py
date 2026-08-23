"""The contract for versioned runtime prompt packs."""

from abc import ABC, abstractmethod

from pydantic import BaseModel, Field


def version_key(version: str) -> tuple[int, tuple[int, ...], str]:
    """Sort key defining what "newest" means, for both ``2.10`` and ``draft``.

    All-numeric versions compare component by component as integers, so ``2.10`` is newer than
    ``2.9`` -- which string ordering gets backwards. Anything else falls back to lexicographic
    and sorts below every numeric version, since a named version is not a claim to be newest.

    This lives beside the contract rather than inside an implementation because
    ``SkillRegistry.versions`` *promises* "newest first", and every implementation has to mean
    the same thing by it. The in-memory fake, the disk registry and the Blob registry each sort
    a different data structure, but they sort it with this. Two answers to "which version is
    newest" only diverge once a pack has a second version, which is late and quiet (D41).
    """
    parts = version.split(".")
    if parts and all(part.isdigit() for part in parts):
        return (1, tuple(int(part) for part in parts), "")
    return (0, (), version)


class SkillPack(BaseModel):
    """A versioned pack of instructions the pipeline loads at runtime.

    ``content`` is **data**. It is interpolated into a prompt and nothing else -- never
    evaluated, never imported, never treated as a template that can reach back into the
    process. A pack that needs to execute is a code change wearing a disguise.
    """

    name: str
    version: str
    content: str
    metadata: dict[str, str] = Field(default_factory=dict)


class SkillRegistry(ABC):
    """Loads prompt packs by name and version.

    The point of putting this behind an interface rather than keeping prompts as string
    constants is that packs live on disk locally and in Blob on Azure, so improving a prompt
    ships without a code deploy or a review cycle. Prompts that require a deploy do not get
    improved; they rot. Versioning is what makes an improvement reversible when it turns out
    to be a regression.

    Note that ``runtime_skills/`` -- what this loads -- is unrelated to ``.claude/skills/``,
    which is build-time instruction for Claude Code. Same word, different audiences.
    """

    @abstractmethod
    async def load(self, name: str, version: str | None = None) -> SkillPack:
        """Return the pack ``name``; ``version`` ``None`` means the newest available.

        Raises:
            SkillPackNotFound: no such pack, or no such version of it.
        """

    @abstractmethod
    async def versions(self, name: str) -> list[str]:
        """Return the available versions of ``name``, newest first per ``version_key``.

        Returns an empty list for an unknown pack rather than raising -- this is the
        question you ask *before* committing to a pack. A *malformed* name is a different
        thing from an unknown one and implementations may reject it; absent is not invalid.
        """

    @abstractmethod
    async def list_packs(self) -> list[str]:
        """Return the names of every pack in the registry, sorted. Empty if there are none."""
