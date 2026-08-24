"""What the LLM returns when asked to write one segment's narration.

Kept separate from ``core/outline_schema.py`` because it answers a different question at a
different point in the pipeline: the outline decides what a segment is about, scripting decides
the words a synthetic voice reads for it -- one call per segment, once the outline exists.

Strict schema, same rules as every other LLM-facing model in this repo: no defaults, no
constraint keywords (a ``max_length`` here would be silently dropped and then enforced nowhere,
per D26), and guidance lives in ``Field(description=...)`` instead.
"""

from pydantic import Field

from core.strict_schema import StrictSchema


class Narration(StrictSchema):
    """One segment's spoken script, as the scripting model wrote it."""

    text: str = Field(
        description="The narration for this segment, written to be spoken aloud -- no "
        "markdown, no bullets, no headings, no parentheses. Roughly 70 to 80 words for a "
        "28-second segment."
    )
