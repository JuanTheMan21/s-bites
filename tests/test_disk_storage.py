"""What ``DiskStorage`` does that no other implementation can be asked about.

The contract itself is covered in ``tests/test_storage_parity.py``, against all three backends at
once. What is left is the half that is *specifically* filesystem: which file a key becomes,
whether that file can be made to sit outside the root, and what a failing disk turns into on the
way out. None of those questions even parse for a dict or for Blob.

The distinction that matters most here is the one at the top of ``get_bytes``: **absent and
unreadable have opposite retry answers.** A missing object is ``ObjectNotFound`` and a retry will
not conjure it; a disk that would not answer is ``ProviderUnavailable`` and a retry might well
work. Both arrive as ``OSError`` from ``pathlib``, so collapsing them is a one-line mistake with
no visible symptom until T14 requeues the wrong things.
"""

from pathlib import Path

import pytest

from adapters.local.storage import DEFAULT_ARTIFACT_ROOT, DiskStorage
from interfaces import ObjectNotFound, ProviderUnavailable


def test_the_root_is_resolved_once_at_construction(tmp_path: Path) -> None:
    """A relative root is anchored to where the process started, not to the working directory.

    ``DiskSkillRegistry`` resolves for the same reason. Anything else means a ``chdir`` anywhere
    in the process silently repoints storage at a different tree.
    """
    assert DiskStorage(Path("artifacts")).root.is_absolute()
    assert DiskStorage(tmp_path / "a" / ".." / "b").root == (tmp_path / "b").resolve()
    assert Path("artifacts") == DEFAULT_ARTIFACT_ROOT


async def test_a_key_becomes_the_path_it_reads_like(tmp_path: Path) -> None:
    """The mapping is worth pinning: T21 serves these and T18's mux reads them by hand."""
    storage = DiskStorage(tmp_path)
    await storage.put_bytes("segments/3/narration.wav", b"audio")

    assert (tmp_path / "segments" / "3" / "narration.wav").read_bytes() == b"audio"


async def test_writes_create_intermediate_directories(tmp_path: Path) -> None:
    """Blob has no directories, so nothing upstream ever creates one. This adapter must."""
    storage = DiskStorage(tmp_path / "not-yet")
    await storage.put_bytes("a/b/c/d.txt", b"x")

    assert await storage.get_bytes("a/b/c/d.txt") == b"x"


async def test_the_url_is_a_real_file_uri(tmp_path: Path) -> None:
    storage = DiskStorage(tmp_path)
    await storage.put_bytes("clip.mp4", b"...")

    url = await storage.url("clip.mp4")

    # `as_uri` percent-encodes and normalises separators, so this is deliberately checking the
    # scheme and the identity rather than reconstructing a path out of the string -- which is
    # exactly what the contract tells callers in `core/` not to do.
    assert url.startswith("file:///")
    assert url.endswith("/clip.mp4")


async def test_expires_is_accepted_and_ignored(tmp_path: Path) -> None:
    """There is no server in front of a disk, so a expiring URL would be a lie about lifetime."""
    storage = DiskStorage(tmp_path)
    await storage.put_bytes("clip.mp4", b"...")

    assert await storage.url("clip.mp4", expires_s=1) == await storage.url("clip.mp4")


async def test_a_failing_write_is_the_backend_failing_not_a_caller_bug(tmp_path: Path) -> None:
    """The disk is this adapter's backend, so a write it refuses is the same class of event as
    a refused Blob request -- and worth the one retry ``ProviderUnavailable`` promises."""
    blocked = tmp_path / "root"
    blocked.write_bytes(b"this is a file, not a directory")
    storage = DiskStorage(blocked)

    with pytest.raises(ProviderUnavailable, match="could not write"):
        await storage.put_bytes("anything.txt", b"...")


async def test_an_unreadable_object_is_not_reported_as_a_missing_one(tmp_path: Path) -> None:
    """Both are ``OSError`` from pathlib, and their retry answers are opposite.

    A directory standing where an object should be is the portable way to get a read that fails
    without the path being absent -- Windows raises ``PermissionError``, POSIX
    ``IsADirectoryError``, and both are ``OSError``.
    """
    storage = DiskStorage(tmp_path)
    (tmp_path / "occupied").mkdir()

    with pytest.raises(ProviderUnavailable, match="could not read"):
        await storage.get_bytes("occupied")


async def test_a_missing_object_is_object_not_found(tmp_path: Path) -> None:
    with pytest.raises(ObjectNotFound, match="never-written"):
        await DiskStorage(tmp_path).get_bytes("never-written")


async def test_exists_is_false_for_a_directory_standing_where_an_object_would_be(
    tmp_path: Path,
) -> None:
    """``is_file`` rather than ``exists``: a directory is not an object, and saying it is would
    let a caller skip a write and then fail to read what it assumed was there."""
    storage = DiskStorage(tmp_path)
    (tmp_path / "occupied").mkdir()

    assert await storage.exists("occupied") is False


def can_symlink(tmp_path: Path) -> bool:
    try:
        (tmp_path / "probe").symlink_to(tmp_path)
    except (OSError, NotImplementedError):
        return False
    return True


async def test_a_symlink_cannot_smuggle_a_key_out_of_the_root(tmp_path: Path) -> None:
    """The containment check earning its place.

    ``check_key`` rejects ``..`` and absolute keys, so through the public API that check is
    otherwise unreachable -- the same known gap ``DiskSkillRegistry._pack_path`` carries. A
    symlink is the one input that passes every key rule and still resolves outside the root,
    which is why it is worth a test rather than a comment.

    Skipped where the platform will not create one: Windows needs Developer Mode or elevation.
    """
    root = tmp_path / "root"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (outside / "secret.txt").write_bytes(b"not yours")
    if not can_symlink(tmp_path):
        pytest.skip("this platform will not create symlinks without elevation")
    (root / "escape").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="resolves outside"):
        await DiskStorage(root).get_bytes("escape/secret.txt")
