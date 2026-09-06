"""Shared plumbing for the ``live`` tests: credentials, and throwaway Blob containers / Service
Bus queues.

Live tests are opt-in (``pytest -m live``) and **skip rather than fail** when a credential is
absent, so a fresh clone with no ``.env`` still runs the suite green. That is the same bargain
``pyproject.toml``'s ``-m 'not live'`` default makes from the other side: offline is the normal
case, and touching Azure is the exception you ask for.

Each live test gets its **own container or queue**, created and deleted around it. Sharing one
would make the assertions order-dependent -- ``list``-shaped checks would see leftovers from
whatever ran before, which is the same trap ``conftest.py`` avoids by scoping every fake to a
single test. Containers and queues are cheap; a test that passes because of what ran before it is
not.

This module talks to the Azure SDK directly rather than through the adapters. That is deliberate:
a fixture that sets up its own subject using the code under test cannot fail honestly.
"""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta
from uuid import uuid4

import pytest
from azure.servicebus.aio.management import ServiceBusAdministrationClient
from azure.storage.blob.aio import BlobServiceClient
from dotenv import load_dotenv

load_dotenv()

CONNECTION_STRING = "AZURE_STORAGE_CONNECTION_STRING"
SERVICE_BUS_CONNECTION_STRING = "AZURE_SERVICE_BUS_CONNECTION_STRING"


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


@asynccontextmanager
async def throwaway_queue() -> AsyncIterator[str]:
    """Create a uniquely named Service Bus queue and delete it after (T34).

    Same reasoning as ``throwaway_container``: ``ServiceBusJobQueue`` parity tests enqueue and
    dequeue by a hardcoded ``job_id`` like ``"job-1"``, so a queue shared across test runs risks a
    dequeue picking up a stale message left by an earlier, differently-asserting test -- a queue's
    own delivery order is not otherwise scoped to any one test. Uses ``azure.servicebus``'s own
    administration client (SAS-authenticated via the same connection string, not the ARM
    management plane), so no extra dependency or credential beyond what ``.env`` already has.
    ``lock_duration``/``max_delivery_count`` mirror the real ``video-jobs`` queue provisioned for
    this project (5-minute lock, 10 deliveries -- above ``api.runner.MAX_ATTEMPTS`` so our own
    dead-lettering decides, not the broker's).
    """
    connection = require(SERVICE_BUS_CONNECTION_STRING)
    name = f"live-{uuid4().hex[:16]}"

    async with ServiceBusAdministrationClient.from_connection_string(connection) as admin:
        await admin.create_queue(name, lock_duration=timedelta(minutes=5), max_delivery_count=10)
        try:
            yield name
        finally:
            await admin.delete_queue(name)


@asynccontextmanager
async def throwaway_topic_subscription() -> AsyncIterator[tuple[str, str]]:
    """Create a uniquely named topic with one subscription, and delete the topic (which cascades
    to its subscription) after. Same isolation reasoning as ``throwaway_queue``, for
    ``ServiceBusEventChannel``.
    """
    connection = require(SERVICE_BUS_CONNECTION_STRING)
    topic_name = f"live-{uuid4().hex[:16]}"
    subscription_name = "test"

    async with ServiceBusAdministrationClient.from_connection_string(connection) as admin:
        await admin.create_topic(topic_name)
        await admin.create_subscription(topic_name, subscription_name)
        try:
            yield topic_name, subscription_name
        finally:
            await admin.delete_topic(topic_name)
