"""Shared plumbing for the ``live`` tests: credentials, and throwaway Blob containers.

Live tests are opt-in (``pytest -m live``) and **skip rather than fail** when a credential is
absent, so a fresh clone with no ``.env`` still runs the suite green. That is the same bargain
``pyproject.toml``'s ``-m 'not live'`` default makes from the other side: offline is the normal
case, and touching Azure is the exception you ask for.

Each live storage test gets its **own container**, created and deleted around it. Sharing one
would make the assertions order-dependent -- ``list``-shaped checks would see leftovers from
whatever ran before, which is the same trap ``conftest.py`` avoids by scoping every fake to a
single test. Containers are cheap; a test that passes because of what ran before it is not.

This module talks to the Azure SDK directly rather than through the adapters. That is deliberate:
a fixture that sets up its own subject using the code under test cannot fail honestly.
"""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import uuid4

import pytest
from azure.storage.blob.aio import BlobServiceClient
from dotenv import load_dotenv

load_dotenv()

CONNECTION_STRING = "AZURE_STORAGE_CONNECTION_STRING"


def require(name: str) -> str:
    """The value of ``name``, or skip. Missing credentials are a reason not to run, not a bug."""
    value = os.environ.get(name, "")
    if not value:
        pytest.skip(f"{name} is not set; copy .env.example to .env and fill it in")
    return value


@asynccontextmanager
async def throwaway_container(blobs: dict[str, str] | None = None) -> AsyncIterator[str]:
    """Create a uniquely named container holding ``{blob name: text}``, and delete it after.

    Yields the container name. Deletion runs in a ``finally`` so a failing assertion still
    cleans up -- an orphaned container is a small cost that compounds every time the suite runs.
    """
    connection = require(CONNECTION_STRING)
    name = f"live-{uuid4().hex[:16]}"

    client = BlobServiceClient.from_connection_string(connection)
    async with client:
        await client.create_container(name)
        try:
            container = client.get_container_client(name)
            for blob_name, text in (blobs or {}).items():
                await container.upload_blob(blob_name, text.encode("utf-8"), overwrite=True)
            yield name
        finally:
            await client.delete_container(name)
