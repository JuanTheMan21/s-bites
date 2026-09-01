"""Which payload field holds an annotation-addressable block's numbered items, and how to read
each item's own short label.

Mirrors ``rendering/annotations.py::_ANNOTATION_TARGET_SUFFIX`` one-for-one -- both name the same
set of block types with numbered sub-elements, one for the id suffix a template emits, one for
the payload field an authoring prompt or a real-item-count check needs. A block type added to
one belongs in the other.

Works against either shape a block's content ever takes: a raw ``dict`` (``ComposedBlock.payload``
before it is validated, D29) or a validated schema instance (``rendering.compose.RenderableBlock
.payload``) -- ``core/graph/nodes/annotation_author.py`` uses the former, ``rendering/
annotations.py`` the latter.
"""

from typing import Any

# Field name, per addressable block type, holding the list of numbered items -- matches
# rendering/annotations.py::_ANNOTATION_TARGET_SUFFIX's own key set exactly. A block type absent
# here (title, stat_callout) has no addressable sub-items.
_ITEM_FIELD: dict[str, str] = {
    "array_grid": "cells",
    "graph_diagram": "nodes",
    "code_panel": "lines",
    "code_diff": "lines",
    "sequence_diagram": "messages",
    "timeline": "events",
    "text_panel": "items",
    "icon_panel": "items",
}


def _field(payload: Any, name: str) -> list[Any]:
    items = payload.get(name) if isinstance(payload, dict) else getattr(payload, name, None)
    return items if items is not None else []


def _item_label(item: Any) -> str:
    """One item's own short display text -- a bare string, or a dict/model's `label`/`text`."""
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        return item.get("label") or item.get("text") or str(item)
    for attr in ("label", "text"):
        value = getattr(item, attr, None)
        if value is not None:
            return value
    return str(item)


def item_labels(block_type: str, payload: Any) -> list[str]:
    """This block's own numbered items, as short display text -- empty for a block type with no
    addressable items, or a payload missing the expected field."""
    field = _ITEM_FIELD.get(block_type)
    if field is None:
        return []
    return [_item_label(item) for item in _field(payload, field)]


def item_count(block_type: str, payload: Any) -> int:
    """How many real, numbered items this block has -- 0 for a block type with no addressable
    items. What an annotation's own ``target_item_index`` must fall inside."""
    return len(item_labels(block_type, payload))
