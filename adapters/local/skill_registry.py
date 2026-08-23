"""``SkillRegistry`` backed by a directory of markdown packs.

The layout is ``<root>/<pack name>/<version>.md`` -- the directory is the pack's name and the
file stem is its version, so adding a version is adding a file and nothing else. That is D4's
point about packs being improvable without a deploy taken literally: no manifest to update, no
index to keep in sync, nothing that can disagree with what is actually on disk.

The file format itself is ``adapters/skill_pack_format``, shared with the Blob registry T11
adds. What is here is only the filesystem: which paths exist, and how a missing one is reported.

**Reads are synchronous inside the ``async def``s, deliberately.** A pack is a few kilobytes and
is read once at the start of a job, so ``asyncio.to_thread`` would cost more in handoff than the
read costs in blocking -- and it would give the appearance of an async filesystem that neither
this adapter nor ``pathlib`` actually has. The Blob registry is genuinely async and awaits for
real; the parity that matters is in the return types and the errors, not in where the work runs.
"""

from pathlib import Path

from adapters.skill_pack_format import PACK_SUFFIX, check_pack_name, check_version, parse_pack
from interfaces import (
    ProviderUnavailable,
    SkillPack,
    SkillPackNotFound,
    SkillRegistry,
    version_key,
)

DEFAULT_SKILLS_ROOT = Path("runtime_skills")


class DiskSkillRegistry(SkillRegistry):
    """Prompt packs read from ``root``, one directory per pack.

    ``config.py`` names this class at T13 and passes the root; nothing else in the repo is
    permitted to. An absent root is an empty registry rather than an error, because a checkout
    with no packs yet is a legitimate state and ``list_packs`` is how a caller finds that out.
    """

    def __init__(self, root: Path = DEFAULT_SKILLS_ROOT) -> None:
        # Resolved once, at construction: a relative default is anchored to the working
        # directory the process started in, not to whatever it happens to be at call time.
        self.root = Path(root).resolve()

    async def load(self, name: str, version: str | None = None) -> SkillPack:
        available = self._versions(name)
        if not available:
            raise SkillPackNotFound(f"no skill pack named {name!r}")

        wanted = check_version(version) if version is not None else available[0]
        if wanted not in available:
            raise SkillPackNotFound(
                f"skill pack {name!r} has no version {wanted!r}; available: {available}"
            )
        return parse_pack(name, wanted, self._read(self._pack_path(name, wanted)))

    async def versions(self, name: str) -> list[str]:
        return self._versions(name)

    async def list_packs(self) -> list[str]:
        if not self.root.is_dir():
            return []
        entries = self._listing(self.root)
        return sorted(child.name for child in entries if child.is_dir())

    def _versions(self, name: str) -> list[str]:
        """Every version of ``name``, newest first. Empty for a pack that is not here.

        ``check_pack_name`` runs first and raises on a malformed name even though this method
        is documented never to raise for an unknown one. Absent and invalid are different
        questions (D39): answering ``../../secrets`` with an empty list would report a
        traversal attempt as an ordinary miss.
        """
        directory = self.root / check_pack_name(name)
        if not directory.is_dir():
            return []

        entries = self._listing(directory, f"*{PACK_SUFFIX}")
        found = [path.stem for path in entries if path.is_file()]
        return sorted(found, key=version_key, reverse=True)

    def _listing(self, directory: Path, pattern: str | None = None) -> list[Path]:
        """List ``directory``, translating a listing that fails into an adapter error.

        The call and the iteration are both inside the ``try`` on purpose. ``iterdir`` and
        ``glob`` are generators, so an ``OSError`` surfaces when the first entry is pulled
        rather than at the call -- which is how a raw ``FileNotFoundError`` escaped ``versions``
        and broke its promise never to raise for a pack that is merely absent. Catching only at
        iteration would leave the eager case uncovered, and which of the two a filesystem gives
        you is not something this adapter should have to know.

        An unreadable directory is the backend failing, not a pack being absent, so it gets the
        same translation a failed read does rather than a misleading empty list.
        """
        try:
            entries = directory.glob(pattern) if pattern is not None else directory.iterdir()
            return list(entries)
        except OSError as exc:
            raise ProviderUnavailable(f"could not list {directory}: {exc}") from exc

    def _pack_path(self, name: str, version: str) -> Path:
        """The file holding one version, checked to be inside the root.

        Both halves are already validated by the time this runs, so the containment check is
        belt and braces. It stays because this is the one place in the project where a caller's
        string becomes a filesystem path, and that is worth two lines of paranoia.
        """
        path = (self.root / name / f"{version}{PACK_SUFFIX}").resolve()
        if not path.is_relative_to(self.root):
            raise ValueError(f"skill pack {name!r} at {version!r} resolves outside {self.root}")
        return path

    def _read(self, path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            # A ValueError, not an AdapterError: the backend answered, the data is malformed.
            raise ValueError(f"skill pack at {path} is not valid UTF-8") from exc
        except OSError as exc:
            # The disk is this adapter's backend, so a failed read is the same class of event
            # as a failed Blob request -- and both are worth one retry.
            raise ProviderUnavailable(f"could not read skill pack at {path}: {exc}") from exc
