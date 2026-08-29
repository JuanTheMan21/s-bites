"""``CODE_DIFF``'s content schema. Split out for the same reason as the other T18C block schema
modules -- see ``core/block_schemas_graph.py``'s docstring.

Direct port of the HyperFrames registry's ``code-diff`` component's framing ("removed lines
collapse in red, added lines expand in green") -- the one exact registry name-match this task's
research found, hand-ported per D103's established rule (the registry's own clone mechanism
doesn't fit this project's composition model), not installed as-is.
"""

from pydantic import Field

from core.block_types import CodeDiffOp
from core.strict_schema import StrictSchema


class CodeDiffLine(StrictSchema):
    """One line of a diff."""

    op: CodeDiffOp = Field(
        description="CONTEXT for an unchanged line shown for orientation, ADD for a line the "
        "change introduces, REMOVE for a line the change deletes."
    )
    text: str = Field(
        description="The line's own source text, without a leading +/-/space -- the template "
        "supplies that marker from op."
    )


class CodeDiffSlots(StrictSchema):
    """A before/after change to a piece of code, shown as one continuous diff."""

    headline: str = Field(description="What this change does or fixes. A short phrase.")
    language: str = Field(description="Language name for syntax highlighting, e.g. 'python'.")
    lines: list[CodeDiffLine] = Field(
        description="The diff, top to bottom, CONTEXT/ADD/REMOVE lines interleaved as they'd "
        "appear in a real diff. Keep under about fourteen lines."
    )
    caption: str | None = Field(
        description="One sentence saying what the change fixes or breaks, or null if the diff "
        "speaks for itself."
    )
