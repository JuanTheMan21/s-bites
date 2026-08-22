"""What the LLM returns when asked to plan a video, and how that becomes pipeline state.

Kept separate from ``core/models.py`` because the two are governed by different rules. These
are strict schemas -- no defaults, no constraint keywords, every field required -- while
``Segment`` and ``VideoJob`` are ours to fill and carry defaults freely. The dependency runs one
way, this module onto ``core.models``, so the enums have a single home.

The separation is also Invariant 1 made structural: there is no timing field here for the model
to fill, so the rule that duration comes from measured audio is not left to prompt wording.
"""

from pydantic import Field

from core.models import Importance, Segment, VisualIntent
from core.strict_schema import StrictSchema


class SegmentPlan(StrictSchema):
    """One segment as the outline model proposes it: title, subject, visual, weight.

    Everything here is a judgement the LLM is qualified to make. What it is not qualified to
    decide -- how long the narration actually turned out to be, which tier that earned -- lives
    on ``Segment`` instead.
    """

    title: str = Field(description="Short segment title, a few words. Shown to the viewer.")
    summary: str = Field(
        description="One or two sentences naming the single idea this segment teaches. This is "
        "what the scripting step will narrate; it is not the narration itself."
    )
    visual_intent: VisualIntent = Field(
        description="The kind of visual that best carries this particular idea."
    )
    importance: Importance = Field(
        description="How central this segment is to the topic, 1 (aside) to 5 (the point of the "
        "video). Decides which segments earn the richest rendering, so spread these out -- "
        "rating everything 5 spends the budget on nothing in particular."
    )

    def to_segment(self, index: int) -> Segment:
        """An unnarrated, unmeasured, untiered segment built from what the LLM proposed.

        Every field this does *not* set is the point: narration, duration, tier and slots stay
        ``None`` until the stage that legitimately knows each one has run.
        """
        return Segment(index=index, **self.model_dump())


class Outline(StrictSchema):
    """The whole outline, one object wrapping the list.

    The wrapper is not decoration: strict mode requires an object at the schema root, so a call
    that wants a list has to ask for a model containing one.
    """

    segments: list[SegmentPlan] = Field(description="The segments, in the order they play.")
