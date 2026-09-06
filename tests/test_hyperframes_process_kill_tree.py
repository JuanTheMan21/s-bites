"""``adapters/local/hyperframes_process.py::_kill_tree``'s platform split (T35).

Found while planning the container image, not by any test: the POSIX branch did not exist before
this task, so a stalled render inside a Linux container silently leaked orphaned Chrome processes
on every timeout (see the function's own docstring). Mocked entirely -- no real subprocess, and
``os.killpg``/``os.getpgid``/``signal.SIGKILL`` don't exist at all on Windows (verified running
this file: referencing ``signal.SIGKILL`` as a plain attribute raises ``AttributeError`` on this
interpreter regardless of what ``sys.platform`` is monkeypatched to), which is exactly why all
three must be patched in rather than exercised for real on the dev machine -- the production code
is unaffected, since the real deployment target is Linux, where all three genuinely exist.
"""

import sys

from adapters.local import hyperframes_process

_SIGKILL = getattr(hyperframes_process.signal, "SIGKILL", 9)


class _FakeProc:
    def __init__(self, pid: int) -> None:
        self.pid = pid
        self.killed = False

    def kill(self) -> None:
        self.killed = True

    async def wait(self) -> int:
        return 0


async def test_posix_kills_the_whole_process_group(monkeypatch) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(hyperframes_process.signal, "SIGKILL", _SIGKILL, raising=False)
    calls = []
    monkeypatch.setattr(hyperframes_process.os, "getpgid", lambda pid: pid * 10, raising=False)
    monkeypatch.setattr(
        hyperframes_process.os, "killpg", lambda pgid, sig: calls.append((pgid, sig)), raising=False
    )

    proc = _FakeProc(pid=42)
    await hyperframes_process._kill_tree(proc)

    assert calls == [(420, _SIGKILL)]
    assert proc.killed  # the existing proc.kill() fallback still runs after the group kill


async def test_posix_tolerates_a_process_already_gone(monkeypatch) -> None:
    """`os.getpgid` raises `ProcessLookupError` for a pid that no longer exists -- must not
    propagate, and the existing `proc.kill()` fallback must still run."""
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(hyperframes_process.signal, "SIGKILL", _SIGKILL, raising=False)
    # os.killpg is never actually reached (getpgid raises first) -- patched anyway so the plain
    # attribute lookup Python does to resolve the callable doesn't itself AttributeError on
    # Windows, where os.killpg doesn't exist at all (unlike real Linux, where it does).
    monkeypatch.setattr(hyperframes_process.os, "killpg", lambda *a: None, raising=False)

    def _raise(*_args):
        raise ProcessLookupError

    monkeypatch.setattr(hyperframes_process.os, "getpgid", _raise, raising=False)

    proc = _FakeProc(pid=42)
    await hyperframes_process._kill_tree(proc)  # must not raise

    assert proc.killed


async def test_run_passes_start_new_session_on_posix_but_not_windows(monkeypatch) -> None:
    """Found by review, not by any test: the POSIX branch of `_kill_tree` is only safe *because*
    `run()` isolates the child into its own process group first. Without `start_new_session=True`,
    the child inherits this process's own group, and `os.killpg` on a timeout would SIGKILL the
    caller itself (the api/worker container process) instead of just the orphaned render -- a
    strictly worse failure than the leak this task fixes. Pinning the coupling directly, since
    `test_posix_kills_the_whole_process_group` above exercises `_kill_tree` in isolation and can't
    catch a future refactor that silently drops this kwarg from `run()`."""
    monkeypatch.setattr(hyperframes_process, "_base_command", lambda: ["hyperframes"])

    class _FakeCommunicateProc:
        def __init__(self, pid: int) -> None:
            self.pid = pid
            self.returncode = 0

        async def communicate(self) -> tuple[bytes, bytes]:
            return b"", b""

    captured_kwargs: dict = {}

    async def fake_create_subprocess_exec(*_args, **kwargs):
        captured_kwargs.update(kwargs)
        return _FakeCommunicateProc(pid=1)

    monkeypatch.setattr(
        hyperframes_process.asyncio, "create_subprocess_exec", fake_create_subprocess_exec
    )

    monkeypatch.setattr(sys, "platform", "linux")
    await hyperframes_process.run(["x"], context="test", timeout_s=5)
    assert captured_kwargs.get("start_new_session") is True

    captured_kwargs.clear()
    monkeypatch.setattr(sys, "platform", "win32")
    await hyperframes_process.run(["x"], context="test", timeout_s=5)
    assert "start_new_session" not in captured_kwargs


async def test_windows_still_uses_taskkill_not_the_posix_path(monkeypatch) -> None:
    """Existing behaviour, pinned so this change cannot silently regress it."""
    monkeypatch.setattr(sys, "platform", "win32")
    posix_calls = []
    monkeypatch.setattr(
        hyperframes_process.os, "killpg", lambda *a: posix_calls.append(a), raising=False
    )

    taskkill_argv = []

    async def fake_create_subprocess_exec(*args, **kwargs):
        taskkill_argv.append(args)
        return _FakeProc(pid=99)

    monkeypatch.setattr(
        hyperframes_process.asyncio, "create_subprocess_exec", fake_create_subprocess_exec
    )

    proc = _FakeProc(pid=42)
    await hyperframes_process._kill_tree(proc)

    assert taskkill_argv == [("taskkill", "/T", "/F", "/PID", "42")]
    assert posix_calls == []
    assert proc.killed
