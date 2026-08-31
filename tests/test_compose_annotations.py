"""T18C's cross-cutting annotation overlay -- offline, no browser, no CLI.

Split out of ``tests/test_compose_scene.py`` once adding these pushed that file over the
200-line ceiling. Annotations are not indexed by ``BlockType`` the way every other block-level
test file is (see ``core/scene_schemas.py::ComposedAnnotation``'s docstring for why they are a
separate concept), so nothing in that file's own parametrized sweeps exercises them.

T18E, D121/D122: every annotation now names a real item and a real narration moment, or it is
dropped -- there is no longer a "whole block" or "beat after entrance" fallback. These tests were
rewritten for that; the old fallback test is gone, replaced by the two new ways an annotation is
dropped (a bad item index, an unresolvable anchor) alongside the one that survives from before
(a bad block index).
"""

from pathlib import Path

from core.block_types import BlockType
from core.scene_schemas import ComposedAnnotation, ComposedBlock, ComposedScene
from interfaces.tts_provider import WordMark
from rendering.compose import compose_scene
from tests.block_examples import EXAMPLES
from tests.segment_examples import a_segment

DURATION_MS = 21_000

# "The parser cannot tell data from code." -- TEXT_PANEL's own item[1] in tests/block_examples.py,
# reused verbatim as a resolvable anchor_phrase and word_marks pair.
_ANCHOR_PHRASE = "cannot tell data from code"
_WORD_MARKS = [
    WordMark(text=word, offset_ms=i * 300, duration_ms=250)
    for i, word in enumerate(["The", "parser", "cannot", "tell", "data", "from", "code."])
]


def _segment_with_annotation(annotation: ComposedAnnotation, *, word_marks=_WORD_MARKS):
    scene = ComposedScene(
        motif="terminal",
        layout="single",
        blocks=[
            ComposedBlock(
                block_type=BlockType.TEXT_PANEL,
                role="role",
                anchor_phrase=None,
                payload=EXAMPLES[BlockType.TEXT_PANEL],
            )
        ],
        continues_previous=False,
        annotations=[annotation],
    )
    return a_segment(0, duration_ms=DURATION_MS).model_copy(
        update={"scene": scene.model_dump(), "word_marks": word_marks}
    )


def test_an_annotation_targets_its_real_element_id_and_the_right_container(tmp_path: Path) -> None:
    """An annotation targeting a real item resolves through
    ``rendering.annotations._ANNOTATION_TARGET_SUFFIX`` to the real id that block's own template
    emits for that item, and (for SINGLE) is wired to render inside #stage."""
    annotation = ComposedAnnotation(
        annotation_type="cursor",
        target_block_index=0,
        target_item_index=1,
        anchor_phrase=_ANCHOR_PHRASE,
        caption="right here",
    )
    segment = _segment_with_annotation(annotation)

    dest = compose_scene(segment, tmp_path)
    html = dest.read_text(encoding="utf-8")

    assert "hfAnnotationPlace(" in html
    assert '"b0-row-1"' in html
    assert '"stage"' in html
    assert '"b0-headline"' in html
    assert "right here" in html


def test_an_out_of_range_block_target_is_dropped_silently(tmp_path: Path) -> None:
    """Nothing in strict-mode structured output can be forced to stay in range -- the same
    defensive-default reasoning ``visual_plan.py::_fallback_scene`` applies to a segment plan's
    own index. A composition with a dangling target must still compose, minus that annotation."""
    annotation = ComposedAnnotation(
        annotation_type="warning",
        target_block_index=5,
        target_item_index=0,
        anchor_phrase=_ANCHOR_PHRASE,
        caption="unreachable",
    )
    segment = _segment_with_annotation(annotation)

    dest = compose_scene(segment, tmp_path)
    html = dest.read_text(encoding="utf-8")

    assert "unreachable" not in html
    assert "anno-warn-wrap" not in html


def test_an_out_of_range_item_index_is_dropped_silently(tmp_path: Path) -> None:
    """T18E: TEXT_PANEL's example payload has exactly 3 items (indices 0-2) -- index 7 names
    nothing real, so the annotation is dropped rather than landing on a guessed element."""
    annotation = ComposedAnnotation(
        annotation_type="check",
        target_block_index=0,
        target_item_index=7,
        anchor_phrase=_ANCHOR_PHRASE,
        caption="off the end",
    )
    segment = _segment_with_annotation(annotation)

    dest = compose_scene(segment, tmp_path)
    html = dest.read_text(encoding="utf-8")

    assert "off the end" not in html
    assert "anno-check-wrap" not in html


def test_an_unresolvable_anchor_phrase_is_dropped_silently(tmp_path: Path) -> None:
    """T18E: a wrong annotation is worse than a missing one -- an anchor_phrase that does not
    appear in this segment's narration is no longer kept with a guessed fallback beat."""
    annotation = ComposedAnnotation(
        annotation_type="cursor",
        target_block_index=0,
        target_item_index=1,
        anchor_phrase="words that were never actually said",
        caption="phantom",
    )
    segment = _segment_with_annotation(annotation)

    dest = compose_scene(segment, tmp_path)
    html = dest.read_text(encoding="utf-8")

    assert "phantom" not in html
    assert "anno-cursor-wrap" not in html
