"""``ARRAY_GRID``'s content schema. Split out of ``core/block_schemas.py`` (T18C) for the same
"crosses the 200-line ceiling once every T18C block is added" reason as ``block_schemas_graph``.

T18C generalizes T18B's ``ArrayEliminationStep`` (renamed ``ArrayStep``) beyond pure narrowing:
a sliding window needs to translate its range, not just shrink it, and a stack/queue needs to
grow or shrink by exactly one cell at its own acting end. ``op`` says which of those four things
happened; ``end_operation`` is a separate, optional iconography badge at the acting end.
"""

from pydantic import Field

from core.block_types import ArrayOrientation, ArrayStepOp, EndMarker
from core.strict_schema import StrictSchema


class ArrayStep(StrictSchema):
    """One moment the array's active range changes."""

    op: ArrayStepOp = Field(
        description="NARROW: the range shrinks from either/both ends without translating (a "
        "binary search's halving). SHIFT: the range translates by its own fixed width (a "
        "sliding window advancing). PUSH: the range's end grows by exactly one cell, revealing "
        "a value entering the structure (a stack push, a queue enqueue). POP: the range's end "
        "shrinks by exactly one cell, removing what was there (a stack pop, a queue dequeue)."
    )
    anchor_phrase: str = Field(
        description="A short phrase copied VERBATIM from this segment's narration, marking the "
        "moment this change happens."
    )
    remaining_start: int = Field(
        description="Index (0-based) of the first cell in the active range after this step."
    )
    remaining_end: int = Field(
        description="Index (0-based, EXCLUSIVE) after this step. For NARROW, must sit inside "
        "the previous step's range. For SHIFT, the width (remaining_end - remaining_start) must "
        "equal the previous step's width. For PUSH, remaining_end must be exactly one more than "
        "the previous step's; remaining_start unchanged. For POP, remaining_end must be exactly "
        "one less; remaining_start unchanged."
    )
    end_operation: EndMarker = Field(
        description="An iconography badge ('+' or '-') shown at the acting end of this step -- "
        "PLUS for a cell entering (PUSH, SHIFT's leading edge), MINUS for a cell leaving (POP, "
        "SHIFT's trailing edge), NONE for a plain NARROW that already reads clearly from its "
        "own strike-through."
    )


class ArrayGridSlots(StrictSchema):
    """A row (or column) of cells, optionally changing over time."""

    headline: str = Field(description="What this array or list represents. A short phrase.")
    orientation: ArrayOrientation = Field(
        description="HORIZONTAL for most arrays and lists. VERTICAL when the content reads more "
        "naturally top-to-bottom, e.g. a call stack."
    )
    cells: list[str] = Field(
        description="The array's items, in order, as short labels (a value, a name). Keep to "
        "twelve or fewer so each cell stays readable at a glance."
    )
    steps: list[ArrayStep] = Field(
        description="Zero or more moments, in narration order, where the active range changes. "
        "Leave empty for a static array with nothing eliminated, shifted, pushed, or popped."
    )
