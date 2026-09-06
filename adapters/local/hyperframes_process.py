"""Shared process plumbing for shelling out to the HyperFrames Node CLI.

Split out of ``hyperframes_cli.py`` (T18A) once a second caller (``hyperframes_check.py``) needed
the identical spawn/timeout/kill-tree behavior -- the same reason ``mux/ffmpeg_run.py`` exists
rather than each mux module reimplementing subprocess handling.

The repo root's ``package.json`` (T18A) pins the exact hyperframes version and installs it locally
-- an unpinned ``npx hyperframes`` re-resolved the CLI on every call (0.8.10 -> 0.8.12 -> 0.8.15
across three tasks, per D96), and version drift produced non-deterministic ``check``/``lint``
results. The local bin is preferred when present; ``npx`` remains the fallback for an environment
that has not run ``npm install`` yet, so this module degrades rather than hard-failing.
"""

import asyncio
import contextlib
import os
import shutil
import signal
import sys
from pathlib import Path

from adapters.local.render_errors import translate
from interfaces import RenderFailed

_REPO_ROOT = Path(__file__).resolve().parents[2]
_LOCAL_BIN = (
    _REPO_ROOT
    / "node_modules"
    / ".bin"
    / ("hyperframes.cmd" if sys.platform == "win32" else "hyperframes")
)


def _base_command() -> list[str]:
    """The argv prefix for invoking hyperframes: the pinned local bin, or ``npx`` as a fallback."""
    if _LOCAL_BIN.exists():
        return [str(_LOCAL_BIN)]
    npx = shutil.which("npx")
    if npx is None:
        raise RenderFailed(
            "'npx' is not on PATH and no pinned local install was found at "
            f"{_LOCAL_BIN} -- the HyperFrames CLI needs Node.js, or `npm install` at the repo root"
        )
    return [npx, "hyperframes"]


async def run(
    args: list[str],
    *,
    context: str,
    timeout_s: float,
    subcommand: str = "render",
    allow_nonzero: bool = False,
) -> str:
    """Invoke ``hyperframes <subcommand> <args>``, returning stdout."""
    command = _base_command()

    try:
        proc = await asyncio.create_subprocess_exec(
            *command,
            subcommand,
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            # POSIX only -- puts the child in its own process group so `_kill_tree` can kill the
            # whole group (node plus whatever chrome-headless-shell it spawned) on a timeout.
            # Windows's kill path (taskkill /T) walks the PID tree instead and needs nothing here.
            **({} if sys.platform == "win32" else {"start_new_session": True}),
        )
    except Exception as exc:
        raise translate(exc, context=context) from exc

    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout_s)
    except Exception as exc:
        # A retry after a timeout would otherwise start a second hyperframes process pointed at
        # the same destination while this one is still running -- kill the whole tree, not just
        # the top PID, since npx wraps node in a small process tree and Process.kill() alone
        # leaves node (and any chrome-headless-shell it spawned) running.
        await _kill_tree(proc)
        raise translate(exc, context=context) from exc

    if proc.returncode != 0 and not allow_nonzero:
        detail = stderr.decode(errors="replace") or stdout.decode(errors="replace")
        raise RenderFailed(f"{context}: hyperframes exited {proc.returncode}: {detail[-2000:]}")
    return stdout.decode(errors="replace")


async def _kill_tree(proc: asyncio.subprocess.Process) -> None:
    """Best-effort kill of ``proc`` and everything it spawned.

    **Found by review, not by any test, while planning T35's container image:** the POSIX branch
    below did not exist until now. Without it, a stalled render on Linux never actually killed
    anything but the top-level process -- `OSError` from the Windows-only `taskkill` call was
    caught and silently swallowed, and the fallback `proc.kill()` only ever reached the direct
    child, leaving node (and any chrome-headless-shell it spawned) running forever. Every render
    timeout in a container leaked one more orphaned Chrome process. `run()`'s own
    `start_new_session=True` on POSIX is what makes `os.killpg` below actually reach the whole
    tree rather than just `proc`'s own PID.
    """
    if sys.platform == "win32":
        try:
            killer = await asyncio.create_subprocess_exec(
                "taskkill",
                "/T",
                "/F",
                "/PID",
                str(proc.pid),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await killer.wait()
        except OSError:
            pass  # taskkill unavailable, or the process already exited
    else:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    with contextlib.suppress(ProcessLookupError):
        proc.kill()
    with contextlib.suppress(Exception):
        await proc.wait()
