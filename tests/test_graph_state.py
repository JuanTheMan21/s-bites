"""``merge_segments`` in isolation -- the reducer that lets concurrent fan-out tasks write to the
same ``segments`` channel without LangGraph refusing the write."""

from core.graph.state import merge_segments
from core.models import Importance, Segment, VisualIntent


def _segment(index: int) -> Segment:
    return Segment(
        index=index,
        title=f"s{index}",
        summary="",
        visual_intent=VisualIntent.TITLE_CARD,
        importance=Importance.NORMAL,
    )


def test_disjoint_updates_from_concurrent_tasks_all_survive() -> None:
    existing = {0: _segment(0)}
    update = {1: _segment(1)}

    merged = merge_segments(existing, update)

    assert set(merged) == {0, 1}


def test_an_update_to_an_existing_index_overwrites_it() -> None:
    original = _segment(0)
    updated = original.model_copy(update={"duration_ms": 9_000})

    merged = merge_segments({0: original}, {0: updated})

    assert merged[0].duration_ms == 9_000


def test_an_empty_update_leaves_existing_state_untouched() -> None:
    existing = {0: _segment(0)}

    assert merge_segments(existing, {}) == existing
