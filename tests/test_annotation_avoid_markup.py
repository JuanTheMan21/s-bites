"""T18K/D164: every text-bearing element on a block type an annotation can actually target now
carries ``data-anno-avoid``, so ``rendering/templates/_annotations.html``'s
``hfEnsureAvoidRects`` has something to register. This is a markup regression test, not a proof
of runtime collision avoidance -- that needs a real browser (``hyperframes check``/Playwright),
covered separately, not in this offline suite.
"""

import pytest

from core.block_types import BlockType
from core.scene_schemas import ComposedBlock, ComposedScene
from rendering.compose import compose_scene
from tests.block_examples import EXAMPLES
from tests.segment_examples import a_segment

DURATION_MS = 21_000

# Every block type ``rendering/annotations.py::_ANNOTATION_TARGET_SUFFIX`` lists as addressable --
# these are the only block types an annotation can ever land on, so they're the only ones that
# need a real ``data-anno-avoid`` marker for the fix to matter.
_ADDRESSABLE_BLOCK_TYPES = [
    BlockType.ARRAY_GRID,
    BlockType.GRAPH_DIAGRAM,
    BlockType.CODE_PANEL,
    BlockType.CODE_DIFF,
    BlockType.SEQUENCE_DIAGRAM,
    BlockType.TIMELINE,
    BlockType.TEXT_PANEL,
    BlockType.ICON_PANEL,
]


def _composed(block_type, tmp_path):
    scene = ComposedScene(
        motif="terminal",
        layout="single",
        blocks=[
            ComposedBlock(
                block_type=block_type,
                role="only",
                anchor_phrase=None,
                payload=EXAMPLES[block_type],
            )
        ],
        continues_previous=False,
    )
    segment = a_segment(0, duration_ms=DURATION_MS).model_copy(update={"scene": scene.model_dump()})
    dest = compose_scene(segment, tmp_path)
    return dest.read_text(encoding="utf-8")


@pytest.mark.parametrize("block_type", _ADDRESSABLE_BLOCK_TYPES, ids=lambda b: b.value)
def test_every_addressable_block_type_marks_its_own_text_for_annotation_avoidance(
    block_type: BlockType, tmp_path
) -> None:
    html = _composed(block_type, tmp_path)
    assert "data-anno-avoid" in html, (
        f"{block_type.value}'s own template marks no text-bearing element data-anno-avoid -- "
        "an annotation on a different item of this block type can land directly on this text "
        "with nothing to stop it (D164)."
    )


def test_hf_ensure_avoid_rects_is_available_wherever_annotations_can_place(tmp_path) -> None:
    """The scanning function itself must be emitted alongside every composition, not just the
    markup it scans -- both halves of the fix have to ship together."""
    html = _composed(BlockType.TEXT_PANEL, tmp_path)
    assert "hfEnsureAvoidRects" in html
    assert "__hfAvoidRects" in html
