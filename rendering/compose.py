"""Turning a scene-authored ``Segment`` into an HTML composition file.

Per D2, the LLM never wrote HTML -- ``core/graph/nodes/scene_author.py`` filled a small slot
payload, and this is where that payload becomes markup, through the matching Jinja template in
``rendering/templates/``. The template file name is the intent's own value
(``VisualIntent.TITLE_CARD.value == "title_card"`` -> ``title_card.html``), the exact convention
``/newintent`` step 3 already documents -- so a new intent with no template fails loudly
(``jinja2.TemplateNotFound``) rather than needing a second mapping to stay in sync.

The composition always lands as the sole file ``dest_dir/index.html``: ``hyperframes lint`` (D60)
hard-requires that literal name and that it be alone in its directory, so this is not a preference,
it is what makes every composition this module writes lint-able at all.
"""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from core.models import Segment
from core.slot_schemas import slot_schema_for

_TEMPLATES_DIR = Path(__file__).parent / "templates"

_env = Environment(
    loader=FileSystemLoader(_TEMPLATES_DIR),
    autoescape=select_autoescape(["html"]),
)


def compose_scene(segment: Segment, dest_dir: Path) -> Path:
    """Render ``segment``'s slots through its visual intent's template, write it, return the path.

    Validates ``segment.slots`` back through ``slot_schema_for(segment.visual_intent)`` (D29 --
    the dict is untyped on ``Segment``, so this is "the point of use" the model's docstring names)
    before it ever reaches a template, so a malformed payload raises pydantic's own
    ``ValidationError`` here rather than surfacing as a confusing Jinja ``AttributeError`` mid-render.

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

    template = _env.get_template(f"{segment.visual_intent.value}.html")
    html = template.render(slots=slots, duration_sec=segment.duration_ms / 1000)

    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "index.html"
    dest.write_text(html, encoding="utf-8")
    return dest
