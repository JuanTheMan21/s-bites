"""``SkillRegistry``, holding packs in a dictionary."""

from collections.abc import Iterable

from interfaces import SkillPack, SkillPackNotFound, SkillRegistry, version_key
from tests.fakes.failure_injection import FailureInjector


class FakeSkillRegistry(FailureInjector, SkillRegistry):
    """In-memory prompt packs, keyed by name and version.

    ``version_key`` is imported rather than defined here, which is the whole point of T7's
    change to it (D41): this fake and ``DiskSkillRegistry`` now answer "which version is
    newest" out of one definition, so they cannot drift apart on a pack's second version.
    ``tests/test_skill_registry_parity.py`` runs the same assertions over both.
    """

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
