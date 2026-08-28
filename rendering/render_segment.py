"""The entry point tying composition, linting, and the three capture tiers together.

Not wired into ``core/graph/`` -- T17 owns rendering, not the pipeline shape. Whichever future
task (T18) drives this per segment supplies its own artifact-layout convention, the way
``core/graph/nodes/synthesize.py`` supplies ``SEGMENT_AUDIO_KEY`` for narration; this module only
needs explicit ``composition_dir``/``dest`` paths from its caller.
"""

from pathlib import Path

from core.models import Segment, Tier
from interfaces import CompositionInvalid, RenderBackend
from rendering.animated import render_animated
from rendering.compose import compose_scene
from rendering.reveal import render_reveal
from rendering.static import render_static

_TIER_RENDERERS = {
    Tier.STATIC: render_static,
    Tier.REVEAL: render_reveal,
    Tier.ANIMATED: render_animated,
}


async def render_segment(
    segment: Segment,
    render: RenderBackend,
    *,
    composition_dir: Path,
    dest: Path,
    fps: int,
) -> Path:
    """Compose, lint, and render ``segment``'s scene at its assigned tier. Returns ``dest``.

    Requires ``segment.duration_ms``, ``segment.tier``, and ``segment.scene`` all set -- the same
    structural enforcement ``core/graph/nodes/scene_author.py::author_scene`` uses, so a caller
    who has skipped a pipeline stage fails here with a clear message rather than composing a scene
    against an invented duration or an absent tier.

    T18B: no longer takes ``job_id`` -- palette selection now comes from the scene's own motif
    (``ComposedScene.motif``, chosen once per video by ``plan_visuals``), not a hash of the job
    id, so ``compose_scene`` needs nothing from this caller beyond the segment itself.

    Raises:
        ValueError: one of the three required fields above is unset.
        CompositionInvalid: ``render.lint`` returned an ``[error]``-severity finding (T18A:
            ``[warning]``/``[info]`` findings do not block the render -- see the inline comment
            at the lint call for why). This project's "catch it
            at write time, no repair loop" stance (D2), applied uniformly before all three tiers
            rather than only before Tier 2, since lint is cheap and a broken composition is
            equally wrong screenshotted as rendered.
    """
    missing = [
        name
        for name, value in (
            ("duration_ms", segment.duration_ms),
            ("tier", segment.tier),
            ("scene", segment.scene),
        )
        if value is None
    ]
    if missing:
        raise ValueError(
            f"segment {segment.index} is missing {missing} -- render_segment requires a fully "
            "measured, tiered, and scene-authored segment."
        )

    composition = compose_scene(segment, composition_dir)

    findings = await render.lint(composition)
    # T18A: was "any finding is fatal" -- found wrong the first time a real render hit a genuine
    # [warning] (composition_file_too_large, once captions/palette pushed a template past
    # hyperframes' own line-count nag). A stylistic warning is not the class of bug D2's
    # no-repair-loop stance exists to catch; only [error] blocks the render, matching the same
    # error/warning distinction `hyperframes check --strict` (errors only) vs `--strict-all`
    # (warnings too) already draws, default is the former. lint()'s own format is
    # "[severity] code: message" (hyperframes_cli.lint), so this is a prefix check, not a new
    # structured return type -- changing that would touch the RenderBackend ABC and Azure's stub.
    fatal = [f for f in findings if not f.startswith("[warning]") and not f.startswith("[info]")]
    if fatal:
        raise CompositionInvalid(
            f"segment {segment.index}'s composition ({composition}) failed lint: {fatal}"
        )

    renderer = _TIER_RENDERERS[segment.tier]
    return await renderer(render, composition, dest, duration_ms=segment.duration_ms, fps=fps)
