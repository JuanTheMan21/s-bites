"""``core/block_triggers.py::missed_block_opportunities`` -- pure, offline. T18D's real-render
matrix found 3 of 6 topics never got the block type they were chosen to stress, and TIMELINE
rendered zero times across the whole matrix (``t18d_catalog.md``); this is the scan
``core/graph/nodes/visual_plan.py`` uses to decide whether a bounded re-ask is worth making.
"""

from core.block_triggers import missed_block_opportunities
from core.block_types import BlockType, MotifName, SceneLayout
from core.scene_plan_schema import PlannedBlock, SegmentScenePlan, VideoScenePlan
from tests.segment_examples import a_segment

TIMELINE_NARRATION = (
    "This is a timeline of the milestones, chronological from the first release to the last "
    "decade of updates."
)


def _plan(*, blocks: dict[int, BlockType]) -> VideoScenePlan:
    return VideoScenePlan(
        motif=MotifName.TERMINAL,
        segments=[
            SegmentScenePlan(
                segment_index=index,
                layout=SceneLayout.SINGLE,
                blocks=[PlannedBlock(block_type=block_type, role="role", anchor_phrase=None)],
                continues_previous=False,
            )
            for index, block_type in blocks.items()
        ],
    )


def test_clear_timeline_vocabulary_with_no_timeline_anywhere_in_the_plan_is_flagged() -> None:
    segment = a_segment(1).model_copy(update={"narration": TIMELINE_NARRATION})
    plan = _plan(blocks={0: BlockType.TITLE, 1: BlockType.TEXT_PANEL})

    missed = missed_block_opportunities([segment], plan)

    assert missed == {1: BlockType.TIMELINE}


def test_a_block_type_already_used_anywhere_in_the_plan_is_never_flagged_again() -> None:
    """Even a segment whose OWN narration is the strongest timeline signal is not flagged if
    some OTHER segment already used TIMELINE -- the scan is about whole-video coverage, not
    per-segment matching."""
    segment_0 = a_segment(0).model_copy(update={"narration": "The title."})
    segment_1 = a_segment(1).model_copy(update={"narration": TIMELINE_NARRATION})
    plan = _plan(blocks={0: BlockType.TIMELINE, 1: BlockType.TEXT_PANEL})

    missed = missed_block_opportunities([segment_0, segment_1], plan)

    assert missed == {}


def test_a_single_generic_word_is_not_enough_of_a_signal() -> None:
    """One hit ('request') is common enough in ordinary narration to be a false positive on its
    own -- the scan requires at least two distinct trigger phrases."""
    segment = a_segment(1).model_copy(
        update={"narration": "There is a request happening here for the user."}
    )
    plan = _plan(blocks={0: BlockType.TITLE, 1: BlockType.TEXT_PANEL})

    missed = missed_block_opportunities([segment], plan)

    assert missed == {}


def test_segment_zero_is_never_flagged() -> None:
    """Segment 0 is always a forced title card (visual_plan.py::_forced_title_scene) -- its own
    narration is irrelevant to block choice."""
    segment_0 = a_segment(0).model_copy(update={"narration": TIMELINE_NARRATION})
    plan = _plan(blocks={0: BlockType.TITLE})

    missed = missed_block_opportunities([segment_0], plan)

    assert missed == {}


def test_a_segment_missing_from_the_plan_is_skipped() -> None:
    """Nothing in strict-mode structured output can force VideoScenePlan.segments to cover every
    index (the same D74 precedent visual_plan.py's own _fallback_scene relies on) -- a segment
    the plan omitted has no primary block to compare against, so the scan leaves it alone."""
    segment = a_segment(1).model_copy(update={"narration": TIMELINE_NARRATION})
    plan = _plan(blocks={0: BlockType.TITLE})  # segment 1 omitted entirely

    missed = missed_block_opportunities([segment], plan)

    assert missed == {}


def test_version_number_chronology_is_flagged_even_with_no_timeline_vocabulary() -> None:
    """T18G, D122 finding 2: the real render's own blind spot -- a narration that signals
    chronology entirely through domain-specific version numbers, never a generic timeline word,
    still went undetected before this fix. None of TRIGGER_VOCABULARY[TIMELINE]'s words appear
    here at all."""
    segment = a_segment(1).model_copy(
        update={
            "narration": (
                "HTTP 1.0 makes one request per connection. HTTP 1.1 keeps the connection "
                "open. HTTP/2 multiplexes several requests at once. HTTP/3 moves the "
                "transport itself onto UDP."
            )
        }
    )
    plan = _plan(blocks={0: BlockType.TITLE, 1: BlockType.TEXT_PANEL})

    missed = missed_block_opportunities([segment], plan)

    assert missed == {1: BlockType.TIMELINE}


def test_a_single_version_number_mentioned_in_passing_is_not_enough() -> None:
    """One version number is not itself a chronology signal -- the scan requires at least three
    distinct ones, the same false-positive guard _MIN_HITS gives the vocabulary scan."""
    segment = a_segment(1).model_copy(
        update={"narration": "The server responds with an HTTP/2 request for the resource."}
    )
    plan = _plan(blocks={0: BlockType.TITLE, 1: BlockType.TEXT_PANEL})

    missed = missed_block_opportunities([segment], plan)

    assert missed == {}
