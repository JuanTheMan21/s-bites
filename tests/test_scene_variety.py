"""``core/scene_variety.py::check_variety`` -- code-level enforcement of the variety rules
``runtime_skills/visual-plan`` has stated in prose since T18C: no block type leading more than a
third of the video, no two consecutive segments sharing a primary block type, and (T18I) a
tighter cap on `sequence_diagram` specifically, from the user's own direct complaint that it is
"used too much, in all videos."""

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


def test_a_varied_compliant_plan_has_no_violations() -> None:
    plan = _plan(
        {
            0: BlockType.TITLE,
            1: BlockType.TEXT_PANEL,
            2: BlockType.GRAPH_DIAGRAM,
            3: BlockType.CODE_PANEL,
            4: BlockType.ARRAY_GRID,
            5: BlockType.STAT_CALLOUT,
        }
    )
    assert check_variety(plan) == []


def test_segment_zero_is_excluded_from_every_check() -> None:
    """Segment 0 is forced to a title card regardless of what the plan says for it
    (``visual_plan.py::_forced_title_scene``) -- a plan where every OTHER segment already
    complies must not be flagged just because segment 0 happens to repeat segment 1's type."""
    plan = _plan({0: BlockType.TEXT_PANEL, 1: BlockType.TEXT_PANEL, 2: BlockType.GRAPH_DIAGRAM})
    assert check_variety(plan) == []


def test_one_type_leading_more_than_a_third_is_flagged() -> None:
    plan = _plan(
        {
            1: BlockType.TEXT_PANEL,
            2: BlockType.TEXT_PANEL,
            3: BlockType.TEXT_PANEL,
            4: BlockType.TEXT_PANEL,
            5: BlockType.GRAPH_DIAGRAM,
            6: BlockType.CODE_PANEL,
        },
        continues={2, 3, 4},
    )
    violations = check_variety(plan)
    assert any("text_panel" in v and "more than a third" in v for v in violations)


def test_a_single_real_segment_never_trips_the_fraction_rule() -> None:
    """One segment is trivially 100% of the video's own primary-block count -- the floor this
    module applies (``max(1, ...)``) exists precisely so a very short plan is not flagged for
    being unable to satisfy a fraction that only makes sense at real video length."""
    plan = _plan({1: BlockType.TEXT_PANEL})
    assert check_variety(plan) == []


def test_consecutive_segments_sharing_a_type_are_flagged() -> None:
    plan = _plan({1: BlockType.GRAPH_DIAGRAM, 2: BlockType.GRAPH_DIAGRAM, 3: BlockType.CODE_PANEL})
    violations = check_variety(plan)
    assert any("segments 1 and 2" in v for v in violations)


def test_consecutive_repeat_is_allowed_when_marked_continues_previous() -> None:
    # Six real segments so two graph_diagram-led ones (33%) stays within the general third-of-
    # the-video cap -- isolating the consecutive-repeat check from the fraction check above.
    plan = _plan(
        {
            1: BlockType.GRAPH_DIAGRAM,
            2: BlockType.GRAPH_DIAGRAM,
            3: BlockType.CODE_PANEL,
            4: BlockType.TEXT_PANEL,
            5: BlockType.ARRAY_GRID,
            6: BlockType.STAT_CALLOUT,
        },
        continues={2},
    )
    assert check_variety(plan) == []


def test_sequence_diagram_is_capped_tighter_than_the_general_rule() -> None:
    """Two sequence_diagram-led segments out of six segments (33%) would pass the general
    third-of-the-video rule, but sequence_diagram's own tighter cap (a fifth) still catches it --
    the user's own direct complaint that it is overused even when nothing else is."""
    plan = _plan(
        {
            1: BlockType.SEQUENCE_DIAGRAM,
            2: BlockType.TEXT_PANEL,
            3: BlockType.SEQUENCE_DIAGRAM,
            4: BlockType.CODE_PANEL,
            5: BlockType.ARRAY_GRID,
            6: BlockType.ICON_PANEL,
        },
    )
    violations = check_variety(plan)
    assert any("sequence_diagram" in v and "capped tighter" in v for v in violations)


def test_one_sequence_diagram_segment_is_always_allowed() -> None:
    plan = _plan({1: BlockType.SEQUENCE_DIAGRAM})
    assert check_variety(plan) == []


def test_an_empty_plan_has_no_violations() -> None:
    plan = VideoScenePlan(motif=MotifName.TERMINAL, segments=[])
    assert check_variety(plan) == []
