"""Shelling out to the HyperFrames Node CLI for full renders and the lint gate.

CLAUDE.md: "HyperFrames is a Node CLI, not a Python library... The render adapter shells out to
it." ``render`` and ``lint`` are the two verbs this module wraps; ``capture`` (Tier 0/1 stills) is
``playwright_capture.py`` instead -- see the module docstring there for why.

**Assumption, not a settled fact (flagged for T17 to confirm):** the CLI validates and renders a
whole *project directory* (``index.html`` plus anything in ``compositions/``), not one arbitrary
file. This module assumes each ``composition`` already lives alone as the sole
``data-composition-id`` file in its own directory -- consistent with the project's per-segment
isolation (D3) -- and that directory's name for the entry file is literally ``index.html``, which
``lint`` has no flag to override. ``render`` accepts ``-c`` so it does not share that constraint,
but both raise loudly rather than silently misbehave if the assumption does not hold.
"""

import asyncio
import contextlib
import json
import shutil
from pathlib import Path

from adapters.local.render_errors import translate
from interfaces import RenderFailed


async def render(
    composition: Path, dest: Path, *, fps: int, quality: str, timeout_s: float
) -> Path:
    """Run ``npx hyperframes render``. Success is exit code 0 and a non-empty ``dest``.

    Not stdout: the CLI's own logging is verbose structured text, not the clean JSON envelope
    ``lint --json`` returns, so parsing it would be reading a log format that is not a contract.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    await _run(
        [
            str(composition.parent),
            "-c",
            composition.name,
            "-o",
            str(dest),
            "--fps",
            str(fps),
            "--quality",
            quality,
            "--quiet",
        ],
        timeout_s=timeout_s,
        context=f"render {composition}",
    )
    if not dest.exists() or dest.stat().st_size == 0:
        raise RenderFailed(
            f"render {composition}: hyperframes exited 0 but wrote no video to {dest}"
        )
    return dest


async def lint(composition: Path, *, timeout_s: float) -> list[str]:
    """Run ``npx hyperframes lint --json``. Never raises for an invalid composition."""
    if composition.name != "index.html":
        raise RenderFailed(
            f"lint {composition}: hyperframes lint always validates a project's index.html, not "
            f"an arbitrary filename -- {composition.name!r} must be renamed to 'index.html' in "
            "its own project directory before this adapter can lint it"
        )

    stdout = await _run(
        ["--json", str(composition.parent)],
        subcommand="lint",
        timeout_s=timeout_s,
        context=f"lint {composition}",
        allow_nonzero=True,
    )
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise RenderFailed(
            f"lint {composition}: could not parse hyperframes' JSON output: {exc}"
        ) from exc

    # A structural failure (e.g. no index.html found) reports ok=false with an empty findings
    # list and a top-level `error` -- that is lint not having run, not the composition being
    # invalid, and conflating the two would return `[]` for a project the tool never inspected.
    if not payload.get("ok", True) and not payload.get("findings") and payload.get("error"):
        raise RenderFailed(f"lint {composition}: hyperframes could not run: {payload['error']}")

    return [
        f"[{finding.get('severity', 'error')}] {finding.get('code', 'unknown')}: "
        f"{finding.get('message', '')}"
        for finding in payload.get("findings", [])
    ]


async def _run(
    args: list[str],
    *,
    context: str,
    timeout_s: float,
    subcommand: str = "render",
    allow_nonzero: bool = False,
) -> str:
    """Invoke ``npx hyperframes <subcommand> <args>``, returning stdout."""
    npx = shutil.which("npx")
    if npx is None:
        raise RenderFailed(f"{context}: 'npx' is not on PATH; the HyperFrames CLI needs Node.js")

    try:
        proc = await asyncio.create_subprocess_exec(
            npx,
            "hyperframes",
            subcommand,
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except Exception as exc:
        raise translate(exc, context=context) from exc

    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout_s)
    except Exception as exc:
        # A retry after a timeout would otherwise start a second hyperframes process pointed at
        # the same destination while this one is still running -- kill the whole tree, not just
        # the top PID, since npx wraps node in a small process tree on Windows and Process.kill()
        # alone leaves node (and any chrome-headless-shell it spawned) running.
        await _kill_tree(proc)
        raise translate(exc, context=context) from exc

    if proc.returncode != 0 and not allow_nonzero:
        detail = stderr.decode(errors="replace") or stdout.decode(errors="replace")
        raise RenderFailed(f"{context}: hyperframes exited {proc.returncode}: {detail[-2000:]}")
    return stdout.decode(errors="replace")


async def _kill_tree(proc: asyncio.subprocess.Process) -> None:
    """Best-effort kill of ``proc`` and everything it spawned."""
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
        pass  # taskkill unavailable or the process already exited -- proc.kill() below still tries
    with contextlib.suppress(ProcessLookupError):
        proc.kill()
    with contextlib.suppress(Exception):
        await proc.wait()
