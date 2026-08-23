"""``Storage`` backed by Azure Blob, with time-limited SAS URLs.

The same six methods the disk adapter implements, against a service instead of a filesystem.
Three differences are real rather than incidental, and all three are places the contract was
written to accommodate them:

**``content_type`` is stored here and ignored on disk.** A filesystem has nowhere to put it. The
API layer at T21 serves artifacts through this interface, and a video served as
``application/octet-stream`` does not play in a browser -- so the parameter exists for this
adapter's benefit and the disk adapter accepts it as a hint.

**``url`` returns a SAS URL, not a ``file://`` one.** The schemes differ by necessity; the
guarantee that holds on both is the one the contract states -- the string identifies this object
and nothing else. ``expires_s`` is honoured here and ignored on disk.

**Both byte- and file-oriented methods are genuinely used.** Blob speaks bytes; ffmpeg,
Playwright and HyperFrames read and write real files. Committing the interface to one shape
would have forced this adapter or that one to copy through a temporary file on every call.

The async client owns a connection pool, so this class has an ``aclose``. That method is
deliberately *not* on the ``Storage`` contract -- see its docstring.
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path

from azure.core.exceptions import AzureError
from azure.storage.blob import BlobSasPermissions, ContentSettings, generate_blob_sas
from azure.storage.blob.aio import BlobServiceClient

from adapters.azure.blob_errors import translate
from interfaces import ObjectNotFound, Storage, check_key

# Small clock skew allowance on the SAS start time. Without it a URL minted here and used
# immediately can be rejected as not-yet-valid by a node whose clock is a few seconds behind.
CLOCK_SKEW = timedelta(minutes=5)


class BlobStorage(Storage):
    """Objects stored as blobs in one container, addressed by relative POSIX key.

    ``config.py`` names this class at T13 and passes the connection string and container from
    ``AZURE_STORAGE_CONNECTION_STRING`` / ``AZURE_STORAGE_CONTAINER``.
    """

    def __init__(self, connection_string: str, container: str) -> None:
        self.container = container
        self._client = BlobServiceClient.from_connection_string(connection_string)

    async def put_bytes(self, key: str, data: bytes, *, content_type: str | None = None) -> str:
        async with self._blob(key) as blob:
            try:
                await blob.upload_blob(
                    data, overwrite=True, content_settings=_settings(content_type)
                )
            except AzureError as exc:
                raise translate(exc, container=self.container) from exc
        return key

    async def put_file(self, key: str, source: Path, *, content_type: str | None = None) -> str:
        # Opened outside the try: an unreadable source is a caller bug and raises OSError
        # untranslated, per the contract. Dressing it as an AdapterError would earn it a requeue
        # that reproduces the same missing file.
        handle = source.open("rb")
        with handle:
            async with self._blob(key) as blob:
                try:
                    # Streamed, not read whole -- a finished segment MP4 is tens of megabytes.
                    await blob.upload_blob(
                        handle, overwrite=True, content_settings=_settings(content_type)
                    )
                except AzureError as exc:
                    raise translate(exc, container=self.container) from exc
        return key

    async def get_bytes(self, key: str) -> bytes:
        async with self._blob(key) as blob:
            try:
                stream = await blob.download_blob()
                return await stream.readall()
            except AzureError as exc:
                raise translate(exc, container=self.container) from exc

    async def get_file(self, key: str, dest: Path) -> Path:
        data = await self.get_bytes(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return dest

    async def exists(self, key: str) -> bool:
        async with self._blob(key) as blob:
            try:
                return await blob.exists()
            except AzureError as exc:
                raise translate(exc, container=self.container) from exc

    async def url(self, key: str, *, expires_s: int = 3600) -> str:
        if not await self.exists(key):
            # Checked rather than minted blindly: a SAS URL for a blob that does not exist is a
            # perfectly valid string that 404s later, somewhere with less context than here.
            raise ObjectNotFound(f"no object stored at {key!r}")

        credential = self._client.credential
        account_key = getattr(credential, "account_key", None)
        if not account_key:
            raise ObjectNotFound(
                "cannot sign a SAS URL without an account key; the client was built from a "
                "credential that does not carry one"
            )

        now = datetime.now(UTC)
        token = generate_blob_sas(
            account_name=self._client.account_name,
            container_name=self.container,
            blob_name=check_key(key),
            account_key=account_key,
            permission=BlobSasPermissions(read=True),
            start=now - CLOCK_SKEW,
            expiry=now + timedelta(seconds=expires_s),
        )
        return f"{self._client.url.rstrip('/')}/{self.container}/{key}?{token}"

    def _blob(self, key: str):
        """The blob a key means. Validates first, so a malformed key never reaches the wire."""
        return self._client.get_blob_client(self.container, check_key(key))

    async def aclose(self) -> None:
        """Release the underlying connection pool.

        Deliberately not on the ``Storage`` contract. ``DiskStorage`` and ``FakeStorage`` have
        nothing to close, and adding a method to the interface so that two of three
        implementations can no-op it is the "written from one implementation's perspective"
        failure the ``adapter-contract`` skill warns about. The owner of the instance --
        ``config.py`` at T13, the FastAPI lifespan at T19 -- calls this.
        """
        await self._client.close()


def _settings(content_type: str | None) -> ContentSettings | None:
    """``None`` rather than an empty ``ContentSettings``: the latter *clears* the stored type."""
    return ContentSettings(content_type=content_type) if content_type else None
