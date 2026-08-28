"""One content schema per block type, and the registry mapping between them.

Per D2 the LLM never writes HTML. It fills a small structured payload -- a headline, three
items, some array cells -- and a hand-authored Jinja partial (``rendering/templates/
_block_*.html``) turns that into markup. Roughly 100 output tokens against ~1500 for a full
composition, and invalid markup becomes structurally impossible rather than something a repair
loop catches most of the time.

Renamed from ``core/slot_schemas.py`` (T18B): the schemas below are keyed by ``BlockType`` now,
not ``VisualIntent`` -- a block is a fragment of a scene, filled by its own call
(``core/graph/nodes/scene_author.py::fill_block``), not a whole scene chosen once per segment.

Every schema here is an LLM-facing strict schema. Read ``core/strict_schema.py`` before adding
one: no defaults, no length or range constraints, and optionality spelled as an explicit
nullable field. Guidance the model needs goes in ``Field(description=...)``, because that is
what strict mode leaves you.

A block must also degrade to a single static frame, since the tier resolver can put any segment
on Tier 0. That constrains the payloads as much as it constrains the block partials: a schema
whose content only makes sense revealed over time has no Tier 0 form.
"""

from pydantic import Field

from core.block_types import BlockType
from core.strict_schema import StrictSchema


class TitleSlots(StrictSchema):
    """Opening card or section boundary: a statement and an optional qualifier."""

    headline: str = Field(description="The title. A short phrase, ideally under eight words.")
    subtitle: str | None = Field(
        description="A supporting line, or null if the headline stands alone. Null is a normal "
        "answer here -- do not invent a subtitle to fill the field."
    )


class TextPanelSlots(StrictSchema):
    """A claim and the points that support it -- a bullet list on its own, or one side of a
    two-panel comparison when this block is paired with another in a SPLIT_HORIZONTAL layout."""

    headline: str = Field(
        description="What these points are about. A short phrase -- the list's own headline "
        "when alone, or this side's label ('Unsafe', 'Safe') when paired with another panel."
    )
    items: list[str] = Field(
        description="Two to five short points, one short sentence each. When this block is one "
        "side of a comparison, match the other side's item count and keep item *n* addressing "
        "the same dimension as the other panel's item *n*."
    )


class StatCalloutSlots(StrictSchema):
    """A single number, given room to land."""

    value: str = Field(
        description="The number as it should appear, e.g. '94%' or '3.2 billion'. A string, "
        "not a number, because the formatting is part of the message. Still required even when "
        "value_number is set -- it is what a Tier 0/1 still shows, and what value_number's own "
        "count-up lands on."
    )
    unit: str | None = Field(description="A unit or qualifier shown beside the value, or null.")
    context: str = Field(
        description="One sentence saying what the number is and why it matters. Without this "
        "the figure is trivia."
    )
    value_number: float | None = Field(
        description="The plain numeric value `value` renders as, e.g. 200000 for '200,000' -- "
        "or null if `value` is not a clean number a count-up animation would read correctly (a "
        "range, 'about half', an approximation like '3.2 billion' with rounding already baked "
        "in). When set, the animated tier counts up to it live instead of only scaling in."
    )
    prefix: str | None = Field(
        description="Text shown immediately before the counted number, e.g. '$' -- or null. "
        "Only meaningful alongside value_number; ignored otherwise."
    )
    suffix: str | None = Field(
        description="Text shown immediately after the counted number, e.g. 'ms' or '%' -- or "
        "null. Prefer `unit` for a qualifier set apart from the number; use this only for a "
        "symbol that reads as part of the number itself, like '%' or 'x'."
    )


class CodePanelSlots(StrictSchema):
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


class DiagramNode(StrictSchema):
    """One step in a chain diagram."""

    label: str = Field(description="The step itself, two or three words.")
    caption: str | None = Field(
        description="A short clarifying line under the label, or null if the label is clear "
        "on its own."
    )


class DiagramChainSlots(StrictSchema):
    """An ordered process on one straight rail: a request path, an attack chain, a pipeline."""

    headline: str = Field(description="What this chain shows. A short phrase.")
    nodes: list[DiagramNode] = Field(
        description="Three to five steps in order. The template draws the connecting rail "
        "between them, so do not describe the connections as nodes of their own."
    )


class ArrayEliminationStep(StrictSchema):
    """One moment where the array's active range narrows -- a binary search's midpoint check,
    a sliding window closing in, a stack's items popping off one end."""

    anchor_phrase: str = Field(
        description="A short phrase copied VERBATIM from this segment's narration, marking the "
        "moment this elimination happens."
    )
    remaining_start: int = Field(
        description="Index (0-based) of the first cell still in play after this step."
    )
    remaining_end: int = Field(
        description="Index (0-based, EXCLUSIVE -- one past the last cell still in play) after "
        "this step. Must be strictly greater than remaining_start."
    )


class ArrayGridSlots(StrictSchema):
    """A row of cells -- an array, a list, a search space -- optionally narrowing over time."""

    headline: str = Field(description="What this array or list represents. A short phrase.")
    cells: list[str] = Field(
        description="The array's items, left to right, as short labels (a value, a name). "
        "Keep to twelve or fewer so each cell stays readable at a glance."
    )
    steps: list[ArrayEliminationStep] = Field(
        description="Zero or more moments, in narration order, where the range of cells still "
        "in play narrows. Each step's remaining_start/remaining_end must be inside the "
        "previous step's range (or the full array, for the first step) -- the range only ever "
        "shrinks. Leave empty for a static array with nothing eliminated."
    )


# Every block type, its content schema. The coverage test over this mapping is what stops a
# block from being added to the enum without a payload to fill -- a gap that would otherwise
# surface at scene-authoring time, on one topic, minutes into a job.
BLOCK_SCHEMAS: dict[BlockType, type[StrictSchema]] = {
    BlockType.TITLE: TitleSlots,
    BlockType.TEXT_PANEL: TextPanelSlots,
    BlockType.STAT_CALLOUT: StatCalloutSlots,
    BlockType.CODE_PANEL: CodePanelSlots,
    BlockType.DIAGRAM_CHAIN: DiagramChainSlots,
    BlockType.ARRAY_GRID: ArrayGridSlots,
}


def block_schema_for(block_type: BlockType) -> type[StrictSchema]:
    """The schema the scene author asks the LLM to fill for ``block_type``.

    Raises ``KeyError`` on a block type with no schema, which the coverage tests make
    unreachable.
    """
    return BLOCK_SCHEMAS[block_type]
