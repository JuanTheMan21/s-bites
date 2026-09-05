"""``core/scene_variety.py::check_variety``'s `title`-overuse cap -- split from
``test_scene_variety.py`` once that file hit the 200-line ceiling. Found in a real render, not
guessed: 3 of 14 non-opening segments came back as `title`, each a regular content segment with
real narration rendered as a static headline+paragraph instead of progressively revealing its
points -- exactly the user's own complaint on watching it."""

from core.block_types import BlockType, MotifName, SceneLayout
from core.scene_plan_schema import PlannedBlock, SegmentScenePlan, VideoScenePlan
from core.scene_variety import check_variety


def _plan(
    primary_types: dict[int, BlockType], *, continues: set[int] = frozenset()
) -> VideoScenePlan:
    return VideoScenePlan(
        motif=MotifName.TERMINAL,
        segments=[
            SegmentScenePlan(
                segment_index=index,
                layout=SceneLayout.SINGLE,
                blocks=[PlannedBlock(block_type=block_type, role="role", anchor_phrase=None)],
                continues_previous=index in continues,
            )
            for index, block_type in primary_types.items()
        ],
    )


def test_title_overuse_mid_video_is_flagged() -> None:
    """The exact shape a real render produced: 3 of 14 non-opening segments (21%) came back as
    `title`, each a regular content segment with real narration rendered as a static
    headline+paragraph instead of progressively revealing its points."""
    plan = _plan(
        {
            1: BlockType.GRAPH_DIAGRAM,
            2: BlockType.SEQUENCE_DIAGRAM,
            3: BlockType.ICON_PANEL,
            4: BlockType.TITLE,
            5: BlockType.CODE_PANEL,
            6: BlockType.GRAPH_DIAGRAM,
            7: BlockType.ARRAY_GRID,
            8: BlockType.CODE_DIFF,
            9: BlockType.TITLE,
            10: BlockType.TEXT_PANEL,
            11: BlockType.TITLE,
            12: BlockType.TEXT_PANEL,
            13: BlockType.ICON_PANEL,
            14: BlockType.STAT_CALLOUT,
        },
        continues={9, 11},
    )
    violations = check_variety(plan)
    assert any("`title`" in v and "genuine change of subject" in v for v in violations)


def test_a_single_mid_video_title_is_allowed() -> None:
    """One real subject-change moment per video is legitimate -- the cap targets overuse, not
    every mid-video title outright."""
    plan = _plan(
        {
            1: BlockType.GRAPH_DIAGRAM,
            2: BlockType.SEQUENCE_DIAGRAM,
            3: BlockType.ICON_PANEL,
            4: BlockType.TITLE,
            5: BlockType.CODE_PANEL,
            6: BlockType.GRAPH_DIAGRAM,
            7: BlockType.ARRAY_GRID,
            8: BlockType.CODE_DIFF,
            9: BlockType.TEXT_PANEL,
            10: BlockType.STAT_CALLOUT,
        },
    )
    assert check_variety(plan) == []
