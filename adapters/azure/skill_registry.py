"""``SkillRegistry`` backed by a Blob container of markdown packs.

The Azure half of what D4 was actually for: packs live in Blob rather than in the image, so
improving a prompt is uploading a file rather than shipping a deploy. Prompts that require a
deploy do not get improved; they rot.

**This is a fill-in, not a reimplementation.** The bytes are identical to the ones on disk, so
the format lives in ``adapters/skill_pack_format.py`` and is imported here unchanged --
``parse_pack``, ``check_pack_name``, ``check_version``, ``PACK_SUFFIX``. Two consequences the
disk registry paid for in review come free:

* **A malformed name raises ``ValueError`` even from ``versions()``** (D45), which the contract
  otherwise documents as never raising. Absent and invalid are different questions: answering
  ``../../secrets`` with ``[]`` reports a traversal attempt as an ordinary miss.
* **A name may not end in ``.``** (D46). That rule was found on Windows, where a trailing dot is
  stripped resolving a path but not enumerating a directory -- but it is not Windows-specific in
  effect. ``outline.`` and ``outline`` are distinct blob prefixes that list identically under a
  prefix query, which is the same aliasing bug wearing cloud clothes.

The layout mirrors the disk one exactly: the blob name is ``<pack>/<version>.md``, so the prefix
is the pack's name and the stem is its version. No manifest, nothing that can disagree with what
is in the container.

Unlike the disk registry, the awaits here are real -- this genuinely talks to a network. The
parity that matters against ``DiskSkillRegistry`` is in return types and error behaviour, not in
where the work happens (D47).
"""

from azure.core.exceptions import AzureError
from azure.storage.blob.aio import BlobServiceClient

from adapters.azure.blob_errors import translate
from adapters.skill_pack_format import PACK_SUFFIX, check_pack_name, check_version, parse_pack
from interfaces import SkillPack, SkillPackNotFound, SkillRegistry, version_key

DEFAULT_SKILLS_CONTAINER = "runtime-skills"


class BlobSkillRegistry(SkillRegistry):
    """Prompt packs read from a Blob container, one name-prefix per pack.

    ``config.py`` names this class at T13 and passes the connection string and container from
    ``AZURE_STORAGE_CONNECTION_STRING`` / ``AZURE_SKILLS_CONTAINER``.
    """

    def __init__(self, connection_string: str, container: str = DEFAULT_SKILLS_CONTAINER) -> None:
        self.container = container
        self._client = BlobServiceClient.from_connection_string(connection_string)

    async def load(self, name: str, version: str | None = None) -> SkillPack:
        available = await self._versions(name)
        if not available:
            raise SkillPackNotFound(f"no skill pack named {name!r}")

        wanted = check_version(version) if version is not None else available[0]
        if wanted not in available:
            raise SkillPackNotFound(
                f"skill pack {name!r} has no version {wanted!r}; available: {available}"
            )
        return parse_pack(name, wanted, await self._read(f"{name}/{wanted}{PACK_SUFFIX}"))

    async def versions(self, name: str) -> list[str]:
        return await self._versions(name)

    async def list_packs(self) -> list[str]:
        """Every pack name in the container, sorted.

        ``walk_blobs`` with a delimiter returns prefixes rather than every blob, so this costs
        one listing of the pack names instead of one of every version of every pack.
        """
        container = self._client.get_container_client(self.container)
        async with container:
            try:
                found = [
                    item.name.rstrip("/")
                    async for item in container.walk_blobs(delimiter="/")
                    if item.name.endswith("/")
                ]
            except AzureError as exc:
                raise translate(exc, container=self.container) from exc
        return sorted(found)

    async def _versions(self, name: str) -> list[str]:
        """Every version of ``name``, newest first. Empty for a pack that is not here.

        ``check_pack_name`` runs first and raises on a malformed name even though this is
        documented never to raise for an unknown one (D45). The prefix ends in ``/`` so that
        ``outline`` cannot also match blobs belonging to a pack called ``outline-v2``.
        """
        prefix = f"{check_pack_name(name)}/"
        container = self._client.get_container_client(self.container)
        async with container:
            try:
                names = [blob.name async for blob in container.list_blobs(name_starts_with=prefix)]
            except AzureError as exc:
                raise translate(exc, container=self.container) from exc

        found = [
            blob[len(prefix) : -len(PACK_SUFFIX)]
            for blob in names
            if blob.endswith(PACK_SUFFIX) and "/" not in blob[len(prefix) :]
        ]
        return sorted(found, key=version_key, reverse=True)

    async def _read(self, blob_name: str) -> str:
        blob = self._client.get_blob_client(self.container, blob_name)
        async with blob:
            try:
                stream = await blob.download_blob()
                data = await stream.readall()
            except AzureError as exc:
                raise translate(exc, container=self.container) from exc
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError as exc:
            # A ValueError, not an AdapterError: the backend answered, the data is malformed.
            raise ValueError(f"skill pack at {blob_name} is not valid UTF-8") from exc

    async def aclose(self) -> None:
        """Release the underlying connection pool. Not on the contract -- see ``BlobStorage``."""
        await self._client.close()
