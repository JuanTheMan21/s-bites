"""``hyperframes check`` -- lint + runtime + layout + motion + WCAG contrast, one browser session.

T18A: the render adapter previously called only ``render`` and ``lint``, out of ~30 CLI commands.
``check`` is the tool that actually answers "does this scene move for its whole duration" (the
slideshow symptom this task exists to fix) via its motion/frozen-frame sampling, plus a captions
safety zone and a contrast pass -- neither of which ``lint`` covers.

**Deliberately not on the ``RenderBackend`` ABC.** Adding it there would force
``ContainerAppsRenderBackend`` (still T35's stub) to grow a verb it cannot implement yet, breaking
Invariant 4 (adapter parity). This is a build-and-verification tool, called from scripts and the
build's own verification pass -- never from ``core/``.

``hyperframes check`` is documented as non-deterministically flaky at the currently-resolved CLI
version (D96): the same unchanged composition has alternated ``ok: true``/``ok: false`` across
repeated runs. Re-run before treating one red result as ground truth; this module does not retry
automatically, since retrying past a real failure is exactly what would hide one.
"""

import json
from pathlib import Path

from adapters.local import hyperframes_process
from interfaces import RenderFailed

DEFAULT_SAMPLES = 9
DEFAULT_TIMEOUT_S = 90.0


async def check(
    project_dir: Path,
    *,
    samples: int = DEFAULT_SAMPLES,
    at_transitions: bool = True,
    frame_check: bool = True,
    caption_zone: str | None = None,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> dict:
    """Run ``hyperframes check --json`` over ``project_dir``. Returns the parsed JSON payload.

    Never raises on findings -- same contract shape as ``hyperframes_cli.lint``: an invalid or
    poorly-animated composition is expected input, and the caller decides what is fatal. Only
    raises if the tool itself could not run (unparseable output, or a nonzero exit with no JSON).
    """
    args = [
        "--json",
        "--samples",
        str(samples),
    ]
    if at_transitions:
        args.append("--at-transitions")
    if frame_check:
        args.append("--frame-check")
    if caption_zone:
        args += ["--caption-zone", caption_zone]
    args.append(str(project_dir))

    stdout = await hyperframes_process.run(
        args,
        subcommand="check",
        timeout_s=timeout_s,
        context=f"check {project_dir}",
        allow_nonzero=True,
    )
    try:
        return json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise RenderFailed(
            f"check {project_dir}: could not parse hyperframes' JSON output: {exc}"
        ) from exc
