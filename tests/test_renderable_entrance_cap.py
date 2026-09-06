"""T18M: ``rendering/renderable.py``'s cap on a single-block scene's narration-anchored entrance
-- a real render showed an anchor resolving 49% into its own 22s duration, leaving the stage
genuinely empty (every block partial renders ``opacity: 0`` before its tween) for the whole gap.
Unit-level, directly against ``build_renderable``, rather than through full HTML composition
(``tests/test_block_timing_fixes.py`` covers that end-to-end)."""

from core.block_types import BlockType
from core.scene_schemas import ComposedBlock
from interfaces.tts_provider import WordMark
from rendering.renderable import _MAX_ANCHOR_ENTRANCE, build_renderable
from tests.block_examples import EXAMPLES

DURATION_MS = 21_000


def _word_marks(narration: str) -> list[WordMark]:
    words = narration.split()
    marks = []
    offset = 0
    for word in words:
        marks.append(WordMark(text=word, offset_ms=offset, duration_ms=300))
        offset += 400
    return marks


def test_a_late_single_block_anchor_is_capped() -> None:
    narration = "First a filler line. " + " ".join(f"pad{i}" for i in range(10)) + " then it lands"
    word_marks = _word_marks(narration)
    block = ComposedBlock(
        block_type=BlockType.TEXT_PANEL,
        role="only",
        anchor_phrase="then it lands",
        payload=EXAMPLES[BlockType.TEXT_PANEL],
    )

    renderable = build_renderable(
        0, block, word_marks, is_multi_block=False, duration_s=DURATION_MS / 1000
    )

    assert renderable.entrance_start == _MAX_ANCHOR_ENTRANCE


def test_an_early_single_block_anchor_is_untouched() -> None:
    narration = "then it lands right away with plenty more narration after that"
    word_marks = _word_marks(narration)
    block = ComposedBlock(
        block_type=BlockType.TEXT_PANEL,
        role="only",
        anchor_phrase="then it lands",
        payload=EXAMPLES[BlockType.TEXT_PANEL],
    )

    renderable = build_renderable(
        0, block, word_marks, is_multi_block=False, duration_s=DURATION_MS / 1000
    )

    assert renderable.entrance_start == 0.0
    assert renderable.entrance_start < _MAX_ANCHOR_ENTRANCE


def test_a_multi_block_scene_is_unaffected_by_the_cap() -> None:
    narration = "First a filler line. " + " ".join(f"pad{i}" for i in range(10)) + " then it lands"
    word_marks = _word_marks(narration)
    block = ComposedBlock(
        block_type=BlockType.TEXT_PANEL,
        role="one of two",
        anchor_phrase="then it lands",
        payload=EXAMPLES[BlockType.TEXT_PANEL],
    )

    renderable = build_renderable(
        1, block, word_marks, is_multi_block=True, duration_s=DURATION_MS / 1000
    )

    # Multi-block scenes keep the structural, index-based entrance (T18J) -- the anchor's own
    # (late) time is never consulted at all, so the cap is irrelevant here.
    assert renderable.entrance_start == 0.15 + 1 * 0.25
