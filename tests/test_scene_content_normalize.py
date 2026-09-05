"""``core/scene_content_normalize.py::normalize_block_payload`` -- deterministic truncation of a
sequence diagram's own authored message count, since strict-mode structured output cannot enforce
a list length and the schema's own wording alone was not being followed (the user's own direct
complaint, on a real TCP-handshake render)."""

from core.block_types import BlockType
from core.scene_content_normalize import normalize_block_payload


def _messages(n: int) -> list[dict]:
    return [
        {"anchor_phrase": f"phrase {i}", "from_id": "a", "to_id": "b", "label": f"msg {i}"}
        for i in range(n)
    ]


def test_a_short_sequence_diagram_is_unchanged() -> None:
    payload = {"headline": "h", "actors": [], "messages": _messages(3)}
    result = normalize_block_payload(BlockType.SEQUENCE_DIAGRAM, payload)
    assert len(result["messages"]) == 3
    assert result["messages"] == payload["messages"]


def test_a_long_sequence_diagram_is_truncated_to_three() -> None:
    payload = {"headline": "h", "actors": [], "messages": _messages(8)}
    result = normalize_block_payload(BlockType.SEQUENCE_DIAGRAM, payload)
    assert len(result["messages"]) == 3
    assert result["messages"] == _messages(8)[:3]


def test_truncation_does_not_mutate_the_original_payload() -> None:
    payload = {"headline": "h", "actors": [], "messages": _messages(6)}
    normalize_block_payload(BlockType.SEQUENCE_DIAGRAM, payload)
    assert len(payload["messages"]) == 6


def test_other_block_types_are_returned_unchanged() -> None:
    payload = {"headline": "h", "items": []}
    result = normalize_block_payload(BlockType.TEXT_PANEL, payload)
    assert result is payload
