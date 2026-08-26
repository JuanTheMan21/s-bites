"""Turning a scene-authored ``Segment`` into an HTML composition file.

Per D2, the LLM never wrote HTML -- ``core/graph/nodes/scene_author.py`` filled a small slot
payload, and this is where that payload becomes markup, through the matching Jinja template in
``rendering/templates/``. The template file name is the intent's own value
(``VisualIntent.TITLE_CARD.value == "title_card"`` -> ``title_card.html``), the exact convention
``/newintent`` step 3 already documents -- so a new intent with no template fails loudly
(``jinja2.TemplateNotFound``) rather than needing a second mapping to stay in sync.

The composition always lands as ``dest_dir/index.html``: ``hyperframes lint`` (D60) hard-requires
that literal name. A sibling ``gsap.min.js`` (T18A, see below) does not break that -- verified
directly against ``hyperframes check`` -- so this is not a preference, it is what makes every
composition this module writes lint-able at all.
"""

import shutil
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from core.models import Segment
from core.slot_schemas import slot_schema_for
from rendering.palettes import select_palette

_TEMPLATES_DIR = Path(__file__).parent / "templates"
# T18A: every template now references "./gsap.min.js" rather than a jsDelivr CDN URL, so a render
# needs no network egress -- this is the one copy every composition's directory gets its own of.
_VENDORED_GSAP = _TEMPLATES_DIR / "vendor" / "gsap.min.js"

_env = Environment(
    loader=FileSystemLoader(_TEMPLATES_DIR),
    autoescape=select_autoescape(["html"]),
)


def compose_scene(segment: Segment, dest_dir: Path, *, job_id: str | None = None) -> Path:
    """Render ``segment``'s slots through its visual intent's template, write it, return the path.

    Validates ``segment.slots`` back through ``slot_schema_for(segment.visual_intent)`` (D29 --
    the dict is untyped on ``Segment``, so this is "the point of use" the model's docstring names)
    before it ever reaches a template, so a malformed payload raises pydantic's own
    ``ValidationError`` here rather than surfacing as a confusing Jinja ``AttributeError`` mid-render.

    ``job_id`` (T18A) picks this video's palette deterministically via
    ``rendering.palettes.select_palette`` -- ``None`` (a bare template test, or a caller with no
    job context) always lands on the original amber/blue default, so nothing that predates this
    parameter changes appearance. ``segment.word_marks`` (also T18A, may be empty) is passed
    straight through for the caption macros; degrading to an even stagger when empty is each
    template's job, not this function's.

    Raises:
        ValueError: ``segment.duration_ms`` is unmeasured. Timing comes from measured audio only
            (Invariant 1); a caller who has not measured cannot satisfy this function.
        pydantic.ValidationError: ``segment.slots`` does not match its intent's schema.
    """
    if segment.duration_ms is None:
        raise ValueError(
            f"segment {segment.index} has no measured duration_ms, so its scene cannot be "
            "composed -- timing derives only from measured narration audio (Invariant 1)."
        )

    schema = slot_schema_for(segment.visual_intent)
    slots = schema.model_validate(segment.slots or {})
    palette = select_palette(job_id)

    template = _env.get_template(f"{segment.visual_intent.value}.html")
    html = template.render(
        slots=slots,
        duration_sec=segment.duration_ms / 1000,
        palette=palette,
        word_marks=segment.word_marks,
    )

    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "index.html"
    dest.write_text(html, encoding="utf-8")
    shutil.copyfile(_VENDORED_GSAP, dest_dir / "gsap.min.js")
    return dest
