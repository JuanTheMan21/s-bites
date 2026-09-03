"""``core/scene_normalize.py::normalize_layout`` -- structural enforcement of each ``SceneLayout``'s
own block-count rule (T18I, D124's fifth deferred finding: a SINGLE scene stacking multiple large
blocks produced 42 canvas_overflow findings in a real render)."""

from core.block_types import BlockType, SceneLayout
from core.scene_normalize import normalize_layout
from core.scene_schemas import ComposedBlock


def _block(block_type: BlockType = BlockType.TEXT_PANEL) -> ComposedBlock:
    return ComposedBlock(block_type=block_type, role="role", anchor_phrase=None)


def test_single_with_one_block_is_unchanged() -> None:
    blocks = [_block()]
    layout, result = normalize_layout(SceneLayout.SINGLE, blocks)
    assert layout == SceneLayout.SINGLE
    assert result == blocks


def test_single_with_two_blocks_is_promoted_to_split_horizontal() -> None:
    blocks = [_block(BlockType.GRAPH_DIAGRAM), _block(BlockType.TEXT_PANEL)]
    layout, result = normalize_layout(SceneLayout.SINGLE, blocks)
    assert layout == SceneLayout.SPLIT_HORIZONTAL
    assert result == blocks


def test_single_with_three_blocks_keeps_only_the_first() -> None:
    blocks = [
        _block(BlockType.GRAPH_DIAGRAM),
        _block(BlockType.TEXT_PANEL),
        _block(BlockType.CODE_PANEL),
    ]
    layout, result = normalize_layout(SceneLayout.SINGLE, blocks)
    assert layout == SceneLayout.SINGLE
    assert result == blocks[:1]


def test_split_horizontal_with_two_blocks_is_unchanged() -> None:
    blocks = [_block(BlockType.GRAPH_DIAGRAM), _block(BlockType.TEXT_PANEL)]
    layout, result = normalize_layout(SceneLayout.SPLIT_HORIZONTAL, blocks)
    assert layout == SceneLayout.SPLIT_HORIZONTAL
    assert result == blocks


def test_split_horizontal_with_one_block_keeps_that_one_block() -> None:
    blocks = [_block()]
    layout, result = normalize_layout(SceneLayout.SPLIT_HORIZONTAL, blocks)
    assert layout == SceneLayout.SPLIT_HORIZONTAL
    assert result == blocks


def test_split_horizontal_with_three_blocks_keeps_only_the_first_two() -> None:
    blocks = [
        _block(BlockType.GRAPH_DIAGRAM),
        _block(BlockType.TEXT_PANEL),
        _block(BlockType.CODE_PANEL),
    ]
    layout, result = normalize_layout(SceneLayout.SPLIT_HORIZONTAL, blocks)
    assert layout == SceneLayout.SPLIT_HORIZONTAL
    assert result == blocks[:2]
