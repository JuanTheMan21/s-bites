"""The contract for durable artifact storage."""

from abc import ABC, abstractmethod
from pathlib import Path


def check_key(key: str) -> str:
    """Return ``key`` if it is a usable storage key; raise ``ValueError`` if it is not.

    Keys are ``/``-separated relative POSIX strings. The disk adapter roots them under a
    directory, so an absolute key or a ``..`` climbs out of that root; a backslash becomes a
    literal character in a blob name while silently working as a separator on Windows, so the
    same key would address two different objects depending on the stack. A dict accepts all
    three without complaint, which is why the rule cannot live only in the adapters that would
    be harmed by breaking it.

    This lives beside the contract rather than inside an implementation for the reason D43
    settled for ``version_key``, and it is not merely a preference: ``tests/test_fakes.py`` bans
    ``adapters`` as an import root inside fakes, so a shared module under ``adapters/`` is
    literally unreachable from ``FakeStorage``. ``interfaces/`` is the one home every
    implementation can reach -- and the right one on merits, since the class docstring below is
    where "keys are relative POSIX strings" is *promised*.

    Note this applies to ``exists`` too, which is not a contradiction of "never raises for a
    missing key" (D39): malformed is not the same question as absent. Answering ``../../secrets``
    with ``False`` reports a traversal attempt as an ordinary miss.
    """
    if not key:
        raise ValueError("storage keys cannot be empty")
    if "\\" in key:
        raise ValueError(f"storage keys are POSIX and use '/', not '\\': {key!r}")
    if key.startswith("/") or (len(key) > 1 and key[1] == ":"):
        raise ValueError(f"storage keys are relative, never absolute: {key!r}")
    if ".." in key.split("/"):
        raise ValueError(f"storage keys cannot climb out of the root with '..': {key!r}")
    return key


class Storage(ABC):
    """Durable object storage addressed by key.

    Keys are ``/``-separated relative POSIX strings -- ``segments/3/narration.wav`` -- never
    filesystem paths and never absolute. The local adapter roots them under a directory; the
    Blob adapter treats them as blob names. Callers must not build paths out of them or
    assume a key corresponds to a file that exists locally.

    Both byte-oriented and file-oriented methods exist because both are genuinely needed.
    ffmpeg, Playwright and HyperFrames read and write real files on disk, while Blob speaks
    bytes; committing to one shape would force the other adapter to copy through a temporary
    file on every call, which is exactly the contortion that signals a badly drawn interface.

    Writes overwrite silently. Reads of an absent key raise ``ObjectNotFound`` on every
    implementation -- one returning ``None`` where another raises is the classic parity bug
    and is ruled out here rather than discovered on the cloud path.
    """

    @abstractmethod
    async def put_bytes(self, key: str, data: bytes, *, content_type: str | None = None) -> str:
        """Store ``data`` at ``key``, overwriting any existing object. Returns ``key``."""

    @abstractmethod
    async def put_file(self, key: str, source: Path, *, content_type: str | None = None) -> str:
        """Store the contents of ``source`` at ``key``, overwriting. Returns ``key``.

        ``source`` is left in place. Raises ``OSError`` if it cannot be read -- that is a
        caller bug, not a backend failure, so it is not translated to an ``AdapterError``.
        """

    @abstractmethod
    async def get_bytes(self, key: str) -> bytes:
        """Return the object stored at ``key``.

        Raises:
            ObjectNotFound: no object is stored at ``key``.
        """

    @abstractmethod
    async def get_file(self, key: str, dest: Path) -> Path:
        """Write the object stored at ``key`` to ``dest``. Returns ``dest``.

        ``dest``'s parent directory is created if absent; an existing file is overwritten.

        Raises:
            ObjectNotFound: no object is stored at ``key``.
        """

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Whether an object is stored at ``key``. Never raises for a missing key."""

    @abstractmethod
    async def url(self, key: str, *, expires_s: int = 3600) -> str:
        """Return a URL from which the object at ``key`` can be fetched.

        The value is opaque to ``core/`` -- only the API layer dereferences it. The Blob
        adapter returns a time-limited SAS URL; the local adapter returns a ``file://`` URL
        and ignores ``expires_s``, since there is no server in front of the disk. The scheme
        therefore differs between stacks by necessity; the guarantee that holds on both is
        that the string identifies this object and nothing else.

        Raises:
            ObjectNotFound: no object is stored at ``key``.
        """
