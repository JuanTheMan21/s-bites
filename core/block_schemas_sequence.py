"""``SEQUENCE_DIAGRAM`` and ``TIMELINE``'s content schemas -- combined in one module since both
are small, narration-ordered, "events over time" shapes. Split out for the same reason as the
other T18C block schema modules -- see ``core/block_schemas_graph.py``'s docstring.
"""

from pydantic import Field

from core.strict_schema import StrictSchema


class SequenceActor(StrictSchema):
    """One participant/lane in a sequence diagram."""

    id: str = Field(
        description="A short unique id for this actor/lane -- referenced by messages, never "
        "shown to the viewer."
    )
    label: str = Field(description="The actor's own name atop its lane, e.g. 'Client', 'API'.")


class SequenceMessage(StrictSchema):
    """One message sent between two actors."""

    anchor_phrase: str = Field(
        description="A short phrase copied VERBATIM from this segment's narration, marking the "
        "moment this message is sent."
    )
    from_id: str = Field(description="The id of the sending actor.")
    to_id: str = Field(description="The id of the receiving actor.")
    label: str = Field(description="What this message is, two to five words, on the arrow.")


class SequenceDiagramSlots(StrictSchema):
    """Actors/lanes with messages passing between them over time -- a protocol, handshake, or
    request-response exchange."""

    headline: str = Field(description="What this exchange shows. A short phrase.")
    actors: list[SequenceActor] = Field(
        description="Two to five participants, left to right in the order their lanes should "
        "appear."
    )
    messages: list[SequenceMessage] = Field(
        description="The exchange, in narration order. At most 3 messages -- a real, watched "
        "render found more than that reads as hard to follow (this project's own user, on a TCP "
        "handshake). Choose the 3 that matter most; a longer exchange needs a different block, "
        "not more lines here. core/scene_content_normalize.py truncates to the first 3 if this "
        "is ignored, so a longer answer loses its own tail rather than failing outright."
    )


class TimelineEvent(StrictSchema):
    """One labelled event on a timeline."""

    anchor_phrase: str = Field(
        description="A short phrase copied VERBATIM from this segment's narration, marking the "
        "moment this event is described."
    )
    label: str = Field(description="The event itself, a short phrase.")
    date_label: str = Field(
        description="A short marker for when this happened -- a year, a date, or a relative "
        "marker like 'Day 3' -- shown beside the event, not parsed."
    )


class TimelineSlots(StrictSchema):
    """A horizontal run of labelled events, in chronological order."""

    headline: str = Field(description="What this timeline covers. A short phrase.")
    events: list[TimelineEvent] = Field(
        description="Three to seven events, left to right in chronological order -- the order "
        "given is the order drawn, never re-sorted."
    )
