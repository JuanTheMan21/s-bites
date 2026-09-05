"""T18J: `resolve_item_starts` reordering a sortable block's items (D155) silently broke
annotation targeting -- caught by `project-reviewer`, confirmed by reproduction. An annotation's
`target_item_index` is authored against the block's PRE-reorder position
(`core/graph/nodes/annotation_author.py` sees items in authored order, before this reorder ever
runs), but `_annotation_target_id` was building ids from the POST-reorder list position, so a
reordered scene's annotation silently marked whatever item now sat at its old numeric position.

Fixed by threading the permutation `resolve_item_starts` applies through
`RenderableBlock.item_permutation`, and translating an ITEM-kind annotation's `target_item_index`
through it in `rendering/annotations.py::resolve_annotations` before it is ever used.
"""

import re
from pathlib import Path

from core.block_types import AnnotationTargetKind, AnnotationType, BlockType
from core.scene_schemas import ComposedAnnotation, ComposedBlock, ComposedScene
from interfaces.tts_provider import WordMark
from rendering.compose import compose_scene
from tests.segment_examples import a_segment

DURATION_MS = 21_000


def _word_marks(narration: str) -> list[WordMark]:
    words = narration.split()
    marks = []
    offset = 0
    for word in words:
        marks.append(WordMark(text=word, offset_ms=offset, duration_ms=300))
        offset += 400
    return marks


def test_an_annotation_still_marks_its_authored_item_after_a_reorder(tmp_path: Path) -> None:
    """Authored order: [important-item, other-item]. Narration order is reversed, so
    resolve_item_starts swaps them. The annotation was authored with target_item_index=0,
    meaning "the important item" (authored position 0) -- it must still mark that item's text
    after the swap, not whatever now sits at rendered position 0."""
    narration = "Other item spoken first. Important item spoken last."
    word_marks = _word_marks(narration)

    payload = {
        "headline": "h",
        "items": [
            {"text": "THE IMPORTANT ITEM", "anchor_phrase": "important item spoken last"},
            {"text": "the other item", "anchor_phrase": "other item spoken first"},
        ],
    }
    scene = ComposedScene(
        motif="terminal",
        layout="single",
        blocks=[
            ComposedBlock(
                block_type=BlockType.TEXT_PANEL, role="only", anchor_phrase=None, payload=payload
            )
        ],
        continues_previous=False,
        annotations=[
            ComposedAnnotation(
                annotation_type=AnnotationType.CHECK,
                target_block_index=0,
                target_kind=AnnotationTargetKind.ITEM,
                target_item_index=0,  # authored position 0 == "THE IMPORTANT ITEM"
                anchor_phrase="important item spoken last",
                caption=None,
            )
        ],
    )
    segment = a_segment(0, duration_ms=DURATION_MS).model_copy(
        update={"scene": scene.model_dump(), "word_marks": word_marks}
    )

    dest = compose_scene(segment, tmp_path)
    html = dest.read_text(encoding="utf-8")

    # Confirm the reorder actually happened (narration order puts "other" first, "important"
    # last) -- otherwise this test would pass trivially without exercising the fix at all.
    rows = re.findall(r'class="blk-text-copy">([^<]+)</span>', html)
    assert rows == ["the other item", "THE IMPORTANT ITEM"], (
        "expected the reorder to fire so this test actually exercises the permutation fix"
    )

    # The annotation must target the row that now holds "THE IMPORTANT ITEM" (rendered
    # position 1), not rendered position 0 (its old, pre-reorder numeric position).
    important_row_index = rows.index("THE IMPORTANT ITEM")
    annotation_target = re.search(r'hfAnnotationPlace\(\s*"(b0-row-\d+)"', html)
    assert annotation_target is not None, "no CHECK annotation target found in the composed HTML"
    assert annotation_target.group(1) == f"b0-row-{important_row_index}", (
        f"annotation targeted {annotation_target.group(1)!r} but the authored item ended up at "
        f"row {important_row_index} after the reorder"
    )
