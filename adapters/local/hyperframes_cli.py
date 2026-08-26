"""Shelling out to the HyperFrames Node CLI for full renders and the lint gate.

CLAUDE.md: "HyperFrames is a Node CLI, not a Python library... The render adapter shells out to
it." ``render`` and ``lint`` are the two verbs this module wraps; ``capture`` (Tier 0/1 stills) is
``playwright_capture.py`` instead -- see the module docstring there for why. ``check`` (T18A's
second, richer gate) lives in ``hyperframes_check.py`` -- kept separate so this file stays under
the 200-line ceiling and so ``check`` never has to be on the ``RenderBackend`` ABC (Azure's stub
would otherwise need to grow a verb it cannot implement, breaking Invariant 4).

**Assumption, not a settled fact (flagged for T17 to confirm):** the CLI validates and renders a
whole *project directory* (``index.html`` plus anything in ``compositions/``), not one arbitrary
file. This module assumes each ``composition`` already lives alone as the sole
``data-composition-id`` file in its own directory -- consistent with the project's per-segment
isolation (D3) -- and that directory's name for the entry file is literally ``index.html``, which
``lint`` has no flag to override. ``render`` accepts ``-c`` so it does not share that constraint,
but both raise loudly rather than silently misbehave if the assumption does not hold.
"""

import json
from pathlib import Path

from adapters.local import hyperframes_process
from interfaces import RenderFailed

# T18A: heavier compositions (registry blocks, webfonts, WebGL) can miss the CLI's own defaults
# for page navigation (60s) and player-ready (45s) -- raised here, not left at the CLI default,
# because a composition that is merely rich rather than broken should not be indistinguishable
# from one that hung.
BROWSER_TIMEOUT_S = 180
PLAYER_READY_TIMEOUT_MS = 120_000
PROTOCOL_TIMEOUT_MS = 600_000


async def render(
    composition: Path,
    dest: Path,
    *,
    fps: int,
    quality: str,
    timeout_s: float,
    workers: int | str = "auto",
) -> Path:
    """Run ``hyperframes render``. Success is exit code 0 and a non-empty ``dest``.

    Not stdout: the CLI's own logging is verbose structured text, not the clean JSON envelope
    ``lint --json``/``check --json`` return, so parsing it would be reading a log format that is
    not a contract.

    ``workers`` is passed through to ``--workers`` verbatim -- an int pins a worker count, the
    string ``"auto"`` (the CLI's own default) lets it calibrate against the machine.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    await hyperframes_process.run(
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
            "--workers",
            str(workers),
            "--browser-timeout",
            str(BROWSER_TIMEOUT_S),
            "--player-ready-timeout",
            str(PLAYER_READY_TIMEOUT_MS),
            "--protocol-timeout",
            str(PROTOCOL_TIMEOUT_MS),
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
    """Run ``hyperframes lint --json``. Never raises for an invalid composition."""
    if composition.name != "index.html":
        raise RenderFailed(
            f"lint {composition}: hyperframes lint always validates a project's index.html, not "
            f"an arbitrary filename -- {composition.name!r} must be renamed to 'index.html' in "
            "its own project directory before this adapter can lint it"
        )

    stdout = await hyperframes_process.run(
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
