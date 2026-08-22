"""``SkillRegistry``, holding packs in a dictionary."""

from collections.abc import Iterable

from interfaces import SkillPack, SkillPackNotFound, SkillRegistry
from tests.fakes.failure_injection import FailureInjector


def version_key(version: str) -> tuple[int, tuple[int, ...], str]:
    """Sort key making "newest" mean something for both ``2.10`` and ``draft``.

    All-numeric versions compare component by component as integers, so ``2.10`` is newer than
    ``2.9`` -- which string ordering gets backwards. Anything else falls back to lexicographic
    and sorts below every numeric version, since a named version is not a claim to be newest.

    **T7 builds the real registry and must adopt this same rule.** Two different answers to
    "which version is newest" between the fake and the disk-backed implementation is a bug that
    only appears once a pack has more than one version, which is late.
    """
    parts = version.split(".")
    if parts and all(part.isdigit() for part in parts):
        return (1, tuple(int(part) for part in parts), "")
    return (0, (), version)


class FakeSkillRegistry(FailureInjector, SkillRegistry):
    """In-memory prompt packs, keyed by name and version."""

    def __init__(self, packs: Iterable[SkillPack] = ()) -> None:
        self.packs: dict[tuple[str, str], SkillPack] = {(p.name, p.version): p for p in packs}

    def add(self, pack: SkillPack) -> None:
        """Register a pack. Test-only convenience -- the interface has no write side."""
        self.packs[(pack.name, pack.version)] = pack

    async def load(self, name: str, version: str | None = None) -> SkillPack:
        self._maybe_fail("load")
        available = self._versions(name)
        if not available:
            raise SkillPackNotFound(f"no skill pack named {name!r}")

        wanted = version if version is not None else available[0]
        try:
            return self.packs[(name, wanted)]
        except KeyError:
            raise SkillPackNotFound(
                f"skill pack {name!r} has no version {wanted!r}; available: {available}"
            ) from None

    async def versions(self, name: str) -> list[str]:
        self._maybe_fail("versions")
        # Empty list rather than SkillPackNotFound, per the contract: this is the question you
        # ask *before* committing to a pack, so an unknown name is an answer, not a failure.
        return self._versions(name)

    async def list_packs(self) -> list[str]:
        self._maybe_fail("list_packs")
        return sorted({name for name, _ in self.packs})

    def _versions(self, name: str) -> list[str]:
        """Every version of ``name``, newest first."""
        found = [version for pack_name, version in self.packs if pack_name == name]
        return sorted(found, key=version_key, reverse=True)
