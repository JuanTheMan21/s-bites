"""The contract for versioned runtime prompt packs."""

from abc import ABC, abstractmethod

from pydantic import BaseModel, Field


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
        """Return the available versions of ``name``, newest first.

        Returns an empty list for an unknown pack rather than raising -- this is the
        question you ask *before* committing to a pack.
        """

    @abstractmethod
    async def list_packs(self) -> list[str]:
        """Return the names of every pack in the registry, sorted. Empty if there are none."""
