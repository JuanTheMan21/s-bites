"""T18C's cross-cutting annotation overlay -- offline, no browser, no CLI.

Split out of ``tests/test_compose_scene.py`` once adding these pushed that file over the
200-line ceiling. Annotations are not indexed by ``BlockType`` the way every other block-level
test file is (see ``core/scene_plan_schema.py::PlannedAnnotation``'s docstring for why they are a
separate concept), so nothing in that file's own parametrized sweeps exercises them.
"""

from pathlib import Path

from core.block_types import BlockType
from core.scene_schemas import ComposedAnnotation, ComposedBlock, ComposedScene
from rendering.compose import compose_scene
from tests.block_examples import EXAMPLES
from tests.segment_examples import a_segment

DURATION_MS = 21_000


def test_an_annotation_targets_its_real_element_id_and_the_right_container(tmp_path: Path) -> None:
    """An annotation targeting a specific item resolves through
    ``rendering.annotations._ANNOTATION_TARGET_SUFFIX`` to the real id that block's own template
    emits for that item, and (for SINGLE) is wired to render inside #stage."""
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
        annotations=[
            ComposedAnnotation(
                annotation_type="cursor",
                target_block_index=0,
                target_item_index=1,
                anchor_phrase=None,
                caption="right here",
            )
        ],
    )
    segment = a_segment(0, duration_ms=DURATION_MS).model_copy(update={"scene": scene.model_dump()})

    dest = compose_scene(segment, tmp_path)
    html = dest.read_text(encoding="utf-8")

    assert 'hfAnnotationOffset("b0-row-1", "stage")' in html
    assert "right here" in html


def test_an_out_of_range_annotation_target_is_dropped_silently(tmp_path: Path) -> None:
    """Nothing in strict-mode structured output can be forced to stay in range -- the same
    defensive-default reasoning ``visual_plan.py::_fallback_scene`` applies to a segment plan's
    own index. A composition with a dangling target must still compose, minus that annotation."""
    scene = ComposedScene(
        motif="terminal",
        layout="single",
        blocks=[
            ComposedBlock(
                block_type=BlockType.TITLE,
                role="role",
                anchor_phrase=None,
                payload=EXAMPLES[BlockType.TITLE],
            )
        ],
        continues_previous=False,
        annotations=[
            ComposedAnnotation(
                annotation_type="warning",
                target_block_index=5,
                target_item_index=None,
                anchor_phrase=None,
                caption="unreachable",
            )
        ],
    )
    segment = a_segment(0, duration_ms=DURATION_MS).model_copy(update={"scene": scene.model_dump()})

    dest = compose_scene(segment, tmp_path)
    html = dest.read_text(encoding="utf-8")

    assert "unreachable" not in html
    assert "anno-warn-wrap" not in html


def test_an_annotation_with_no_anchor_falls_back_to_a_beat_after_its_targets_entrance(
    tmp_path: Path,
) -> None:
    """No ``anchor_phrase`` and no matching narration both fall back the same way -- a fixed
    delay after the target block's own resolved ``entrance_start``, never t=0."""
    scene = ComposedScene(
        motif="terminal",
        layout="single",
        blocks=[
            ComposedBlock(
                block_type=BlockType.TITLE,
                role="role",
                anchor_phrase=None,
                payload=EXAMPLES[BlockType.TITLE],
            )
        ],
        continues_previous=False,
        annotations=[
            ComposedAnnotation(
                annotation_type="check",
                target_block_index=0,
                target_item_index=None,
                anchor_phrase=None,
                caption=None,
            )
        ],
    )
    segment = a_segment(0, duration_ms=DURATION_MS).model_copy(update={"scene": scene.model_dump()})

    dest = compose_scene(segment, tmp_path)
    html = dest.read_text(encoding="utf-8")

    # b0's own entrance_start falls back to _DEFAULT_ENTRANCE_BASE (0.15) since anchor_phrase is
    # null and there are no word_marks; the annotation's own fallback adds 0.5 on top of that.
    assert "0.65" in html
