"""``Storage`` backed by a directory on disk.

Keys are relative POSIX strings and this adapter roots them under ``root``, so the whole surface
of the thing is one question asked six times: which file does this key mean, and is it still
inside the root? ``interfaces.check_key`` answers the first half and ``_path`` answers the second.

**The containment check is not belt-and-braces here the way it is in ``DiskSkillRegistry``.**
That registry validates a name against a small alphabet before it ever builds a path; a storage
key is a whole ``/``-separated string, legitimately several segments deep, and the only thing
standing between ``../../.ssh/id_rsa`` and a real file is ``check_key`` plus the resolve-and-
compare below. Both, not either.

**Reads and writes are synchronous inside the ``async def``s**, following D47: an artifact is
read once per stage and the thread handoff costs more than the blocking call it avoids. The open
item comes with it -- once T12's asyncio pool runs jobs concurrently on one loop, a slow read
stalls every job sharing that loop rather than only the reader. **Re-check at T12/T13.**

``content_type`` is accepted and ignored. A filesystem has nowhere to put it; the Blob adapter
stores it and serves it back. That asymmetry is real and is why the parameter is documented as a
hint rather than as stored metadata.
"""

import shutil
from pathlib import Path

from interfaces import ObjectNotFound, ProviderUnavailable, Storage, check_key

DEFAULT_ARTIFACT_ROOT = Path("artifacts")


class DiskStorage(Storage):
    """Objects stored as files under ``root``, addressed by relative POSIX key.

    ``config.py`` names this class at T13 and passes the root from ``LOCAL_ARTIFACT_DIR``;
    nothing else in the repo is permitted to.
    """

    def __init__(self, root: Path = DEFAULT_ARTIFACT_ROOT) -> None:
        # Resolved once, at construction, for the reason DiskSkillRegistry resolves its root: a
        # relative default is anchored to the directory the process started in, not to whatever
        # the working directory happens to be when a call arrives.
        self.root = Path(root).resolve()

    async def put_bytes(self, key: str, data: bytes, *, content_type: str | None = None) -> str:
        path = self._path(key)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        except OSError as exc:
            raise ProviderUnavailable(f"could not write {key!r} to {path}: {exc}") from exc
        return key

    async def put_file(self, key: str, source: Path, *, content_type: str | None = None) -> str:
        path = self._path(key)
        # Opening the source is deliberately outside the try: the contract says an unreadable
        # source is a *caller* bug and raises OSError untranslated, because dressing it as an
        # AdapterError would tell T14's retry classifier the backend failed and earn it a requeue
        # that reproduces the same missing file.
        handle = source.open("rb")
        with handle:
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("wb") as destination:
                    # Streamed rather than read whole: a finished segment MP4 is tens of
                    # megabytes and there is no reason for all of it to be resident at once.
                    shutil.copyfileobj(handle, destination)
            except OSError as exc:
                raise ProviderUnavailable(f"could not write {key!r} to {path}: {exc}") from exc
        return key

    async def get_bytes(self, key: str) -> bytes:
        path = self._path(key)
        try:
            return path.read_bytes()
        except FileNotFoundError as exc:
            raise ObjectNotFound(f"no object stored at {key!r}") from exc
        except OSError as exc:
            # The disk is this adapter's backend, so a failed read is the same class of event as
            # a failed Blob request. Distinguished from the line above because "absent" and
            # "unreadable" have opposite retry answers.
            raise ProviderUnavailable(f"could not read {key!r} from {path}: {exc}") from exc

    async def get_file(self, key: str, dest: Path) -> Path:
        path = self._path(key)
        if not path.is_file():
            raise ObjectNotFound(f"no object stored at {key!r}")
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, dest)
        except OSError as exc:
            raise ProviderUnavailable(f"could not copy {key!r} to {dest}: {exc}") from exc
        return dest

    async def exists(self, key: str) -> bool:
        # _path validates, so a malformed key raises here rather than answering False. That is
        # not a contradiction of "never raises for a missing key" (D39): absent and invalid are
        # different questions, and this is the one method where a '..' would otherwise quietly
        # probe outside the root and report the result as an ordinary miss.
        return self._path(key).is_file()

    async def url(self, key: str, *, expires_s: int = 3600) -> str:
        """A ``file://`` URL. ``expires_s`` is ignored -- there is no server in front of a disk.

        The scheme differs from the Blob adapter's SAS URL by necessity. What holds on both is
        the guarantee the contract actually makes: the string identifies this object and nothing
        else.
        """
        path = self._path(key)
        if not path.is_file():
            raise ObjectNotFound(f"no object stored at {key!r}")
        return path.as_uri()

    def _path(self, key: str) -> Path:
        """The file a key means, checked to be inside the root.

        ``check_key`` has already rejected the obvious escapes, but a key is a multi-segment
        string rather than a single validated name, so this is a live check rather than the
        defence-in-depth its counterpart in ``DiskSkillRegistry`` is. A symlink inside the root
        pointing out of it is caught here too, since ``resolve`` follows it before the compare.
        """
        path = (self.root / check_key(key)).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError(f"storage key {key!r} resolves outside {self.root}")
        return path
