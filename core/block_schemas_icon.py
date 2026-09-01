"""``ICON_PANEL``'s content schema. Split out for the same "crosses the 200-line ceiling" reason
as the other block schema modules -- see ``core/block_schemas_graph.py``'s docstring.

T18G, new -- the structural answer to "each topic needs its own visual style," scoped to abstract/
generated graphics (inline SVG icon + label chips) rather than real photo/logo sourcing, which
would need a whole new ``interfaces/``+adapter pair (out of scope for this task, the user's own
choice when planning).
"""

from pydantic import Field

from core.block_types import IconName
from core.strict_schema import StrictSchema


class IconPanelItem(StrictSchema):
    """One icon + label chip."""

    icon: IconName = Field(
        description="The glyph for this concept -- pick the closest match, never a stretch; if "
        "nothing fits, this segment probably isn't an icon_panel segment."
    )
    label: str = Field(description="The concept itself, two or three words.")
    anchor_phrase: str = Field(
        description="A short phrase copied VERBATIM from this segment's narration, marking the "
        "moment this concept should appear."
    )


class IconPanelSlots(StrictSchema):
    """A labelled set of discrete concepts, components, or steps -- more icon-shaped than
    list-shaped ("the three layers of the OSI model," "what a firewall blocks")."""

    headline: str = Field(description="What this set of concepts is. A short phrase.")
    items: list[IconPanelItem] = Field(description="Three to six icon + label chips.")
