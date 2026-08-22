"""What ``FakeStorage`` and ``FakeSkillRegistry`` do.

Paired because they are the same thing at T11: packs live in Blob, addressed by key, behind the
same storage account as every other artifact. Weighted toward the parity-sensitive answers --
raise or return, empty list or exception -- since a fake that is *slightly* more forgiving than
the real adapter is what teaches downstream code the wrong lesson.
"""

from pathlib import Path

import pytest

from interfaces import ObjectNotFound, SkillPack, SkillPackNotFound
from tests.fakes import FakeSkillRegistry, FakeStorage

# --- Storage ------------------------------------------------------------------------------


async def test_objects_round_trip_as_bytes_and_as_files(
    fake_storage: FakeStorage, tmp_path: Path
) -> None:
    """Both shapes exist because ffmpeg and Playwright want files while Blob speaks bytes."""
    source = tmp_path / "narration.wav"
    source.write_bytes(b"audio")

    await fake_storage.put_bytes("segments/0/scene.html", b"<html>")
    await fake_storage.put_file("segments/0/narration.wav", source)

    assert await fake_storage.get_bytes("segments/0/scene.html") == b"<html>"
    assert source.exists(), "put_file leaves the source in place"
    dest = tmp_path / "fetched" / "narration.wav"
    assert await fake_storage.get_file("segments/0/narration.wav", dest) == dest
    assert dest.read_bytes() == b"audio"


async def test_a_missing_key_raises_on_reads_but_not_on_exists(
    fake_storage: FakeStorage, tmp_path: Path
) -> None:
    """The classic parity bug, ruled out: one backend returning None where another raises."""
    assert await fake_storage.exists("nope") is False

    for read in (fake_storage.get_bytes("nope"), fake_storage.url("nope")):
        with pytest.raises(ObjectNotFound, match="nope"):
            await read
    with pytest.raises(ObjectNotFound):
        await fake_storage.get_file("nope", tmp_path / "out.bin")


async def test_writes_overwrite_silently(fake_storage: FakeStorage) -> None:
    await fake_storage.put_bytes("k", b"first")
    await fake_storage.put_bytes("k", b"second")

    assert await fake_storage.get_bytes("k") == b"second"


async def test_a_url_identifies_this_object_and_nothing_else(fake_storage: FakeStorage) -> None:
    """The scheme differs between stacks by necessity; this is the guarantee that holds."""
    await fake_storage.put_bytes("segments/0/clip.mp4", b"...")
    await fake_storage.put_bytes("segments/1/clip.mp4", b"...")

    assert await fake_storage.url("segments/0/clip.mp4") != await fake_storage.url(
        "segments/1/clip.mp4"
    )


@pytest.mark.parametrize(
    "key", ["/segments/0/x.wav", "C:/tmp/x.wav", "segments\\0\\x.wav", "a/../../b", ""]
)
async def test_a_key_the_real_adapters_could_not_honour_is_refused(
    fake_storage: FakeStorage, tmp_path: Path, key: str
) -> None:
    """Keys are relative POSIX strings. An absolute one escapes the disk adapter's root.

    Every method, not just the writes. Checking one of them is how ``exists`` came to be the
    single method that let a malformed key through -- and the one place where a ``..`` would
    have quietly answered for a file outside the root once T11 gave this a real filesystem.
    """
    source = tmp_path / "source.bin"
    source.write_bytes(b"...")

    for call in (
        lambda: fake_storage.put_bytes(key, b"..."),
        lambda: fake_storage.put_file(key, source),
        lambda: fake_storage.get_bytes(key),
        lambda: fake_storage.get_file(key, tmp_path / "out.bin"),
        lambda: fake_storage.exists(key),
        lambda: fake_storage.url(key),
    ):
        with pytest.raises(ValueError, match="storage keys"):
            await call()


async def test_an_unreadable_source_file_is_an_oserror_not_an_adapter_error(
    fake_storage: FakeStorage, tmp_path: Path
) -> None:
    """Documented explicitly on the contract: that is a caller bug, so it is not translated."""
    with pytest.raises(OSError):
        await fake_storage.put_file("k", tmp_path / "does-not-exist.wav")


# --- SkillRegistry ------------------------------------------------------------------------


def a_pack(version: str) -> SkillPack:
    return SkillPack(name="outline", version=version, content=f"outline prompt v{version}")


async def test_loading_without_a_version_gets_the_newest(fake_skills: FakeSkillRegistry) -> None:
    """2.10 is newer than 2.9, which is exactly what string ordering gets wrong.

    **T7 builds the real registry and must sort versions the same way.** Two answers to "which
    is newest" only diverge once a pack has a second version, which is late to find out.
    """
    for version in ("2.9", "1.0", "2.10"):
        fake_skills.add(a_pack(version))

    assert (await fake_skills.load("outline")).version == "2.10"
    assert (await fake_skills.load("outline", "1.0")).version == "1.0"
    assert await fake_skills.versions("outline") == ["2.10", "2.9", "1.0"]


async def test_an_unknown_pack_raises_on_load_but_returns_empty_from_versions(
    fake_skills: FakeSkillRegistry,
) -> None:
    """Asymmetric on purpose: versions() is the question you ask *before* committing."""
    assert await fake_skills.versions("nope") == []
    assert await fake_skills.list_packs() == []

    with pytest.raises(SkillPackNotFound, match="nope"):
        await fake_skills.load("nope")


async def test_a_known_pack_at_an_unknown_version_also_raises(
    fake_skills: FakeSkillRegistry,
) -> None:
    fake_skills.add(a_pack("1.0"))

    with pytest.raises(SkillPackNotFound, match=r"no version '9\.9'"):
        await fake_skills.load("outline", "9.9")
