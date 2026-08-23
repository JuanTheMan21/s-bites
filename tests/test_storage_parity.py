"""The three ``Storage`` implementations, held to one set of assertions.

``tests/test_fake_storage.py`` established what ``FakeStorage`` does; T11 wrote two real adapters
against it, so this is where "identical behavior for put/get/url across both" -- T11's definition
of done, in its own words -- stops being a claim. The same body of assertions runs over a dict, a
filesystem and a Blob container.

The parity traps this rules out are the ones D39 named, and they are all *shapes* of answer
rather than values: one backend returning ``None`` where another raises ``ObjectNotFound``; one
accepting an absolute key that escapes another's root; one reporting a malformed key as an
ordinary miss. Each is invisible in the implementation that gets it wrong and only shows up when
the stacks are compared -- which is here.

``blob`` is marked ``live`` and so is deselected by default. ``fake`` and ``disk`` run offline on
every edit, which is where the great majority of the coverage lives.
"""

from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from adapters.azure.storage import BlobStorage
from adapters.local.storage import DiskStorage
from interfaces import ObjectNotFound, Storage
from tests.azure_live import CONNECTION_STRING, require, throwaway_container
from tests.fakes import FakeStorage

IMPLEMENTATIONS = ["fake", "disk", pytest.param("blob", marks=pytest.mark.live)]

# Every shape that must be refused, from `tests/test_fake_storage.py`. Kept identical on purpose:
# a rejection list the real adapters interpret more loosely than the fake is exactly the drift
# these tests exist to catch.
BAD_KEYS = ["/segments/0/x.wav", "C:/tmp/x.wav", "segments\\0\\x.wav", "a/../../b", ""]


@pytest.fixture(params=IMPLEMENTATIONS)
async def storage(request: pytest.FixtureRequest, tmp_path: Path) -> AsyncIterator[Storage]:
    """One empty store per test, per implementation. Never shared -- these accumulate state."""
    if request.param == "fake":
        yield FakeStorage()
        return
    if request.param == "disk":
        yield DiskStorage(tmp_path / "artifacts")
        return

    async with throwaway_container() as container:
        blob = BlobStorage(require(CONNECTION_STRING), container)
        try:
            yield blob
        finally:
            await blob.aclose()


async def test_objects_round_trip_as_bytes_and_as_files(storage: Storage, tmp_path: Path) -> None:
    """Both shapes exist because ffmpeg and Playwright want files while Blob speaks bytes."""
    source = tmp_path / "narration.wav"
    source.write_bytes(b"audio")

    assert await storage.put_bytes("segments/0/scene.html", b"<html>") == "segments/0/scene.html"
    assert await storage.put_file("segments/0/narration.wav", source) == "segments/0/narration.wav"

    assert await storage.get_bytes("segments/0/scene.html") == b"<html>"
    assert source.exists(), "put_file leaves the source in place"

    dest = tmp_path / "fetched" / "narration.wav"
    assert await storage.get_file("segments/0/narration.wav", dest) == dest
    assert dest.read_bytes() == b"audio"


async def test_a_deeply_nested_key_is_one_object_not_a_directory(storage: Storage) -> None:
    """Keys are opaque strings that happen to contain slashes. Blob has no directories at all."""
    await storage.put_bytes("jobs/abc/segments/12/frames/000.png", b"png")

    assert await storage.exists("jobs/abc/segments/12/frames/000.png")
    assert await storage.exists("jobs/abc/segments/12") is False


async def test_writes_overwrite_silently(storage: Storage, tmp_path: Path) -> None:
    source = tmp_path / "second.bin"
    source.write_bytes(b"second")

    await storage.put_bytes("k", b"first")
    await storage.put_bytes("k", b"second")
    assert await storage.get_bytes("k") == b"second"

    await storage.put_file("k", source)
    assert await storage.get_bytes("k") == b"second"


async def test_get_file_creates_the_destination_directory(storage: Storage, tmp_path: Path) -> None:
    await storage.put_bytes("clip.mp4", b"video")
    dest = tmp_path / "deep" / "not" / "yet" / "clip.mp4"

    assert await storage.get_file("clip.mp4", dest) == dest
    assert dest.read_bytes() == b"video"


async def test_a_missing_key_raises_on_reads_but_not_on_exists(
    storage: Storage, tmp_path: Path
) -> None:
    """The classic parity bug, ruled out: one backend returning None where another raises.

    Code written against an implementation that answers ``None`` handles a value that never
    arrives in production and skips the exception that does.
    """
    assert await storage.exists("nope") is False

    with pytest.raises(ObjectNotFound):
        await storage.get_bytes("nope")
    with pytest.raises(ObjectNotFound):
        await storage.get_file("nope", tmp_path / "out.bin")
    with pytest.raises(ObjectNotFound):
        await storage.url("nope")


async def test_a_url_identifies_this_object_and_nothing_else(storage: Storage) -> None:
    """The scheme differs between stacks by necessity; this is the guarantee that holds."""
    await storage.put_bytes("segments/0/clip.mp4", b"...")
    await storage.put_bytes("segments/1/clip.mp4", b"...")

    first = await storage.url("segments/0/clip.mp4")
    assert first != await storage.url("segments/1/clip.mp4")
    assert "segments/0/clip.mp4" in first


@pytest.mark.parametrize("key", BAD_KEYS)
async def test_a_key_the_real_adapters_could_not_honour_is_refused(
    storage: Storage, tmp_path: Path, key: str
) -> None:
    """All six methods, including ``exists``.

    T6 shipped this rule on five of six and ``project-reviewer`` caught the sixth (D39). The
    general lesson stands: a validation rule tested on one method of six is tested nowhere. And
    ``exists`` refusing a malformed key is not a contradiction of "never raises for a missing
    key" -- absent and invalid are different questions.
    """
    source = tmp_path / "source.bin"
    source.write_bytes(b"...")

    for call in (
        lambda: storage.put_bytes(key, b"..."),
        lambda: storage.put_file(key, source),
        lambda: storage.get_bytes(key),
        lambda: storage.get_file(key, tmp_path / "out.bin"),
        lambda: storage.exists(key),
        lambda: storage.url(key),
    ):
        with pytest.raises(ValueError, match="storage keys"):
            await call()


async def test_an_unreadable_source_file_is_an_oserror_not_an_adapter_error(
    storage: Storage, tmp_path: Path
) -> None:
    """Documented on the contract: a caller bug, so it is not dressed up as a backend failure.

    An ``AdapterError`` here would tell T14's retry classifier the outside world misbehaved, and
    the requeue would reproduce the same missing file on every attempt.
    """
    with pytest.raises(OSError):
        await storage.put_file("k", tmp_path / "does-not-exist.wav")
