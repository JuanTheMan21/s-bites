"""``core/annotation_normalize.py`` -- code-level enforcement of two things the annotation-
authoring skill pack has only ever asked for in prose: a per-scene density cap, and (T18I, no
prose could express this at all) that two or more CURSOR marks on the same block visit it in
narration order, from the user's own direct complaint that a cursor "clicks on some node and not
another" with no visible logic."""

from core.annotation_normalize import cap_video_annotation_budget, normalize_annotations
from core.block_types import AnnotationTargetKind, AnnotationType
from core.scene_schemas import ComposedAnnotation


def _mark(
    annotation_type: AnnotationType = AnnotationType.CHECK,
    *,
    block: int = 0,
    item: int = 0,
    kind: AnnotationTargetKind = AnnotationTargetKind.ITEM,
) -> ComposedAnnotation:
    return ComposedAnnotation(
        annotation_type=annotation_type,
        target_block_index=block,
        target_kind=kind,
        target_item_index=item,
        anchor_phrase="a phrase",
        caption=None,
    )


def test_zero_or_one_annotation_is_unchanged() -> None:
    assert normalize_annotations([]) == []
    marks = [_mark()]
    assert normalize_annotations(marks) == marks


def test_more_than_two_annotations_are_capped_to_the_first_two() -> None:
    marks = [_mark(item=0), _mark(item=1), _mark(item=2)]
    result = normalize_annotations(marks)
    assert result == marks[:2]


def test_a_single_cursor_is_never_flagged_as_incoherent() -> None:
    marks = [_mark(AnnotationType.CURSOR, block=0, item=3)]
    assert normalize_annotations(marks) == marks


def test_cursors_walking_a_block_in_increasing_order_are_kept() -> None:
    marks = [
        _mark(AnnotationType.CURSOR, block=0, item=0),
        _mark(AnnotationType.CURSOR, block=0, item=1),
    ]
    assert normalize_annotations(marks) == marks


def test_cursors_jumping_out_of_order_on_the_same_block_are_all_dropped() -> None:
    """The exact user-reported shape: a cursor lands on one node, then a different one with no
    walk between them. Dropping only the out-of-order mark would still read as a node skipped --
    the whole group goes, not just the offending entry."""
    marks = [
        _mark(AnnotationType.CURSOR, block=0, item=2),
        _mark(AnnotationType.CURSOR, block=0, item=0),
    ]
    assert normalize_annotations(marks) == []


def test_cursors_on_different_blocks_do_not_interfere_with_each_other() -> None:
    marks = [
        _mark(AnnotationType.CURSOR, block=0, item=2),
        _mark(AnnotationType.CURSOR, block=1, item=0),
    ]
    # Only two marks total, each on its own block -- neither is a same-block pair, so neither is
    # incoherent; the cap (two per scene) is what limits this, not the walk-order check.
    assert normalize_annotations(marks) == marks


def test_item_and_link_cursors_on_the_same_block_are_independent_index_spaces() -> None:
    """Caught live by project-reviewer: an ITEM cursor and a LINK cursor share a block but NOT
    a numbering space (core/block_items.py -- a GRAPH_DIAGRAM's nodes and edges are counted
    separately), so a LINK at index 1 followed by an ITEM at index 0 is not "out of order" --
    they are not comparable at all. An earlier version grouped by block alone and dropped both."""
    marks = [
        _mark(AnnotationType.CURSOR, block=0, item=1, kind=AnnotationTargetKind.LINK),
        _mark(AnnotationType.CURSOR, block=0, item=0, kind=AnnotationTargetKind.ITEM),
    ]
    assert normalize_annotations(marks) == marks


def test_cap_and_coherence_apply_together() -> None:
    """A third annotation is dropped by the cap BEFORE the coherence check ever sees it -- the
    surviving two CURSOR marks (items 2, 0) are then out of order and dropped in turn."""
    marks = [
        _mark(AnnotationType.CURSOR, block=0, item=2),
        _mark(AnnotationType.CURSOR, block=0, item=0),
        _mark(AnnotationType.CHECK, block=1, item=0),
    ]
    assert normalize_annotations(marks) == []


def test_budget_keeps_every_segment_when_under_the_fraction() -> None:
    by_segment = {1: [_mark()], 2: [], 3: []}
    assert cap_video_annotation_budget(by_segment) == by_segment


def test_budget_clears_later_segments_once_over_the_fraction() -> None:
    """Five segments, 40% budget -> 2 may carry annotations. Three want to; the two EARLIEST
    (by index) are kept, the rest cleared -- a simple, deterministic tie-break."""
    by_segment = {1: [_mark()], 2: [_mark()], 3: [_mark()], 4: [], 5: []}
    result = cap_video_annotation_budget(by_segment)
    assert result[1] == by_segment[1]
    assert result[2] == by_segment[2]
    assert result[3] == []
    assert result[4] == []
    assert result[5] == []


def test_an_empty_video_has_no_budget_violation() -> None:
    assert cap_video_annotation_budget({}) == {}
