"""One slot payload schema per visual intent, and the registry mapping between them.

Per D2 the LLM never writes HTML. It fills a small structured payload -- a headline, three
bullets, some node labels -- and a hand-authored Jinja template turns that into markup and into
every HyperFrames ``data-*`` attribute. Roughly 100 output tokens against ~1500 for a full
composition, and invalid markup becomes structurally impossible rather than something a repair
loop catches most of the time.

Every schema here is therefore an LLM-facing strict schema. Read ``core/strict_schema.py``
before adding one: no defaults, no length or range constraints, and optionality spelled as an
explicit nullable field. Guidance the model needs -- how long a headline should be, how many
bullets read well -- goes in ``Field(description=...)``, because that is what strict mode
leaves you.

A template must also degrade to a single static frame, since the tier resolver can put any
segment on Tier 0. That constrains the payloads as much as it constrains the templates: a
schema whose content only makes sense revealed over time has no Tier 0 form.
"""

from pydantic import Field

from core.models import VisualIntent
from core.strict_schema import StrictSchema


class TitleCardSlots(StrictSchema):
    """Opening card or section boundary: a statement and an optional qualifier."""

    headline: str = Field(description="The title. A short phrase, ideally under eight words.")
    subtitle: str | None = Field(
        description="A supporting line, or null if the headline stands alone. Null is a normal "
        "answer here -- do not invent a subtitle to fill the field."
    )


class BulletListSlots(StrictSchema):
    """The workhorse: a claim and the points that support it."""

    headline: str = Field(description="What these points are about. A short phrase.")
    bullets: list[str] = Field(
        description="Three to five points, one short sentence each. Fewer than three looks "
        "sparse on screen; more than five will not fit at a readable size."
    )


class ComparisonSlots(StrictSchema):
    """Two things set against each other -- safe against unsafe, before against after."""

    headline: str = Field(description="What is being compared. A short phrase.")
    left_label: str = Field(description="Name of the left-hand side, one or two words.")
    left_items: list[str] = Field(description="Two to four short points about the left side.")
    right_label: str = Field(description="Name of the right-hand side, one or two words.")
    right_items: list[str] = Field(
        description="Two to four short points about the right side. Keep the count matched to "
        "left_items -- the template lays these out as facing rows."
    )


class FlowNode(StrictSchema):
    """One step in a flow diagram."""

    label: str = Field(description="The step itself, two or three words.")
    caption: str | None = Field(
        description="A short clarifying line under the label, or null if the label is clear "
        "on its own."
    )


class DiagramFlowSlots(StrictSchema):
    """An ordered process: a request path, an attack chain, a build pipeline."""

    headline: str = Field(description="What this flow shows. A short phrase.")
    nodes: list[FlowNode] = Field(
        description="Three to five steps in order. The template draws the arrows between them, "
        "so do not describe the connections as nodes of their own."
    )


class CodeWalkthroughSlots(StrictSchema):
    """Source with specific lines called out. The centre of most technical explainers."""

    headline: str = Field(description="What this code does or demonstrates. A short phrase.")
    language: str = Field(description="Language name for syntax highlighting, e.g. 'sql'.")
    lines: list[str] = Field(
        description="The code, one array element per line, without trailing newlines. Keep it "
        "under about twelve lines -- this is an illustration, not a file."
    )
    highlight_lines: list[int] = Field(
        description="Which lines to emphasise, numbered from 1, so 1 is the first element of "
        "lines. Empty list if nothing needs emphasis."
    )
    caption: str | None = Field(
        description="One sentence saying what the highlighted lines mean, or null if the code "
        "speaks for itself."
    )


class StatCalloutSlots(StrictSchema):
    """A single number, given room to land."""

    value: str = Field(
        description="The number as it should appear, e.g. '94%' or '3.2 billion'. A string, "
        "not a number, because the formatting is part of the message."
    )
    unit: str | None = Field(description="A unit or qualifier shown beside the value, or null.")
    context: str = Field(
        description="One sentence saying what the number is and why it matters. Without this "
        "the figure is trivia."
    )


# Every intent, its schema. The pair of coverage tests over this mapping is what stops an
# intent from being added to the enum without a payload to fill -- a gap that would otherwise
# surface at scene-authoring time, on one topic, minutes into a job.
SLOT_SCHEMAS: dict[VisualIntent, type[StrictSchema]] = {
    VisualIntent.TITLE_CARD: TitleCardSlots,
    VisualIntent.BULLET_LIST: BulletListSlots,
    VisualIntent.COMPARISON: ComparisonSlots,
    VisualIntent.DIAGRAM_FLOW: DiagramFlowSlots,
    VisualIntent.CODE_WALKTHROUGH: CodeWalkthroughSlots,
    VisualIntent.STAT_CALLOUT: StatCalloutSlots,
}


def slot_schema_for(intent: VisualIntent) -> type[StrictSchema]:
    """The schema the scene author asks the LLM to fill for ``intent``.

    This is the whole indirection: T16 turns "this segment wants a comparison" into the class
    it hands to ``LLMProvider.generate``, and gets back a validated payload the matching
    template can render. Raises ``KeyError`` on an intent with no schema, which the coverage
    tests make unreachable.
    """
    return SLOT_SCHEMAS[intent]
