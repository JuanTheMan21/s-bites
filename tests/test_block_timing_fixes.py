"""T18J: a multi-block (``SPLIT_HORIZONTAL``) panel's headline waited for the block's own content
anchor -- sometimes most of the way through the segment -- even though both panels are already on
screen from the layout's own tilt-in tween. Confirmed against an actual rendered job's checkpoint
before any fix was written (decisionlog D155 has the exact numbers: 3 of 15 segments, one at 80%
through). Fixed in ``rendering/compose.py::_build_renderable``. Item-reorder and unmatched-anchor
interpolation (the other two defects from the same render) are covered in
``tests/test_item_timing_order.py``.
"""

import re
from pathlib import Path

from core.block_types import BlockType
from core.scene_schemas import ComposedBlock, ComposedScene
from interfaces.tts_provider import WordMark
from rendering.compose import compose_scene
from tests.block_examples import EXAMPLES
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


def _headline_time(html: str, prefix: str) -> float:
    match = re.search(rf'"#{prefix}-headline".*?,\s*([\d.]+)\);', html)
    assert match, f"no headline tween found for {prefix} in the composed HTML"
    return float(match.group(1))


def test_a_split_panel_headline_enters_with_its_panel_not_its_content_anchor(
    tmp_path: Path,
) -> None:
    """The exact live-confirmed defect: a block whose own anchor_phrase matches narration late
    in the segment must not strand its headline until then, once it shares the scene with a
    second panel -- both panels are already visible from the layout's own entrance tween."""
    narration = "First the client sends syn. " + " ".join(f"filler{i}" for i in range(40))
    word_marks = _word_marks(narration)
    late_anchor = " ".join(f"filler{i}" for i in range(35, 40))

    scene = ComposedScene(
        motif="terminal",
        layout="split_horizontal",
        blocks=[
            ComposedBlock(
                block_type=BlockType.TEXT_PANEL,
                role="left",
                anchor_phrase=None,
                payload=EXAMPLES[BlockType.TEXT_PANEL],
            ),
            ComposedBlock(
                block_type=BlockType.TEXT_PANEL,
                role="right",
                # This anchor resolves to word ~37, ~14.8s into a 21s segment (>70% through) --
                # the single-block behavior would correctly strand the headline there; the
                # multi-block behavior must not.
                anchor_phrase=late_anchor,
                payload=EXAMPLES[BlockType.TEXT_PANEL],
            ),
        ],
        continues_previous=False,
    )
    segment = a_segment(0, duration_ms=DURATION_MS).model_copy(
        update={"scene": scene.model_dump(), "word_marks": word_marks}
    )

    dest = compose_scene(segment, tmp_path)
    html = dest.read_text(encoding="utf-8")

    right_headline_time = _headline_time(html, "b1")
    assert right_headline_time < 1.0, (
        f"right panel's headline entered at {right_headline_time}s despite a late content "
        "anchor -- it should enter with its panel, structurally, not on the content anchor"
    )


def test_a_single_block_scene_still_honors_its_own_content_anchor(tmp_path: Path) -> None:
    """The multi-block fix must not regress the single-block case -- there the block IS the
    segment's whole content, so revealing it exactly when the narration introduces it is
    correct choreography, unchanged."""
    narration = (
        "First a filler line. "
        + " ".join(f"pad{i}" for i in range(10))
        + " then the diagram appears here"
    )
    word_marks = _word_marks(narration)

    scene = ComposedScene(
        motif="terminal",
        layout="single",
        blocks=[
            ComposedBlock(
                block_type=BlockType.TEXT_PANEL,
                role="only",
                anchor_phrase="then the diagram appears here",
                payload=EXAMPLES[BlockType.TEXT_PANEL],
            ),
        ],
        continues_previous=False,
    )
    segment = a_segment(0, duration_ms=DURATION_MS).model_copy(
        update={"scene": scene.model_dump(), "word_marks": word_marks}
    )

    dest = compose_scene(segment, tmp_path)
    html = dest.read_text(encoding="utf-8")

    headline_time = _headline_time(html, "b0")
    assert headline_time > 3.0, (
        "a single-block scene's headline should still honor a real, late content anchor"
    )
