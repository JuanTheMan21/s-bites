"""``Storage``, backed by a dictionary."""

from pathlib import Path

from interfaces import ObjectNotFound, Storage
from tests.fakes.failure_injection import FailureInjector


def check_key(key: str) -> None:
    """Reject a key the real adapters could not honour, at the point it is written.

    Keys are ``/``-separated relative POSIX strings. The disk adapter roots them under a
    directory, so an absolute key or a ``..`` escapes that root, and a backslash becomes a
    literal character in a Blob name while silently working as a separator on Windows. A dict
    accepts all three without complaint, which is exactly why the check belongs here: the bug
    would otherwise be invisible until T11 runs the same test against a real backend.
    """
    if not key:
        raise ValueError("storage keys cannot be empty")
    if "\\" in key:
        raise ValueError(f"storage keys are POSIX and use '/', not '\\': {key!r}")
    if key.startswith("/") or (len(key) > 1 and key[1] == ":"):
        raise ValueError(f"storage keys are relative, never absolute: {key!r}")
    if ".." in key.split("/"):
        raise ValueError(f"storage keys cannot climb out of the root with '..': {key!r}")


class FakeStorage(FailureInjector, Storage):
    """In-memory object storage. Writes overwrite; reads of an absent key raise.

    The parity trap this exists to rule out is a fake returning ``None`` where the real adapter
    raises ``ObjectNotFound`` -- code written against that fake handles a ``None`` that never
    arrives in production and skips the exception that does.
    """

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.content_types: dict[str, str | None] = {}

    async def put_bytes(self, key: str, data: bytes, *, content_type: str | None = None) -> str:
        self._maybe_fail("put_bytes")
        check_key(key)
        self.objects[key] = data
        self.content_types[key] = content_type
        return key

    async def put_file(self, key: str, source: Path, *, content_type: str | None = None) -> str:
        self._maybe_fail("put_file")
        check_key(key)
        # An unreadable source raises OSError untranslated: the docstring is explicit that this
        # is a caller bug rather than a backend failure, so it is not an AdapterError.
        self.objects[key] = source.read_bytes()
        self.content_types[key] = content_type
        return key

    async def get_bytes(self, key: str) -> bytes:
        self._maybe_fail("get_bytes")
        return self._read(key)

    async def get_file(self, key: str, dest: Path) -> Path:
        self._maybe_fail("get_file")
        data = self._read(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return dest

    async def exists(self, key: str) -> bool:
        self._maybe_fail("exists")
        # Validated like every other method, though this one answers a question rather than
        # storing anything. "Never raises for a missing key" is a promise about *absence*, and a
        # malformed key is not absent -- it is unanswerable. Letting it through would be the
        # one method on this interface where '..' silently probes outside the storage root.
        check_key(key)
        return key in self.objects

    async def url(self, key: str, *, expires_s: int = 3600) -> str:
        self._maybe_fail("url")
        self._read(key)
        # Opaque, and identifies this object and nothing else -- the only guarantee that holds
        # on both stacks. expires_s is ignored, as it is on the local disk adapter.
        return f"memory://{key}"

    def _read(self, key: str) -> bytes:
        """The lookup every read shares, without re-arming another method's injected failure."""
        check_key(key)
        try:
            return self.objects[key]
        except KeyError:
            raise ObjectNotFound(f"no object stored at {key!r}") from None
