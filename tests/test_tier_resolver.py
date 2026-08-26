"""The tier resolver at full branch coverage, per T6's definition of done.

Two kinds of test live here. The first kind asserts what the resolver *produces* -- that a
realistic outline gets a real spread, that the answer does not depend on input order. The second
asserts what it *refuses*, and those matter more than they look: every one of them is a bug that
would otherwise surface minutes into a job, as a wrong-looking video rather than an error.

``scale_frame_budget`` is tested next door in ``tests/test_frame_budget.py``, mirroring the
module split D35 made -- this file spends a budget, that one decides how large one is.
"""

import random

import pytest

from core import Importance, Tier, VisualIntent, resolve_tiers
from core.tier_resolver import REVEAL_FRAME_COST, TIER_SUPPORT, frame_cost, ideal_tier
from tests.segment_examples import SEVEN_MINUTE_OUTLINE, a_segment, seven_minute_segments


def test_a_tight_budget_still_binds_under_the_t18a_ladder() -> None:
    """D9's actual requirement, re-verified after T18A raised IDEAL_TIER for NORMAL/MINOR.

    The new ladder makes Tier.REVEAL, not Tier.STATIC, the floor every non-ASIDE segment is
    eligible for -- REVEAL_FRAME_COST is flat, so a tight budget still produces genuine
    demotions from the ANIMATED ideal, it just rarely produces a nonzero Tier.STATIC count
    (that only happens if the budget cannot even afford REVEAL's flat per-segment step for
    everyone, which 600 -- generously -- can). The interesting claim now is: some segments are
    demoted, and the plan never overspends.
    """
    plan = resolve_tiers(seven_minute_segments(), frame_budget=600, fps=24)

    assert plan.spread[Tier.STATIC] == 0, "600 easily affords a flat REVEAL step for everyone"
    assert plan.spread[Tier.REVEAL] > 0
    assert plan.frames_used <= plan.frame_budget
    assert plan.demoted, "nothing was demoted, so the budget is not binding"
    assert all(a.ideal is Tier.ANIMATED for a in plan.demoted)


def test_the_budget_buys_shortness_not_importance() -> None:
    """The finding from T5/T16 planning (D32, D78), re-pinned after T18A's ladder correction.

    600 frames at 24fps still buys only ~25 seconds of animation -- one segment's worth -- so
    only the single *shortest* segment (the 9-second title card) reaches Tier 2, regardless of
    importance; every CRITICAL segment is demoted to a reveal because all of them run 30+
    seconds. This is the same shape of finding D78 already made about FRAME_BUDGET=600 being
    too small for real narration -- it is why T18A corrects the environment's FRAME_BUDGET
    rather than the ladder in this module (see the decisionlog's correction to D16).
    """
    plan = resolve_tiers(seven_minute_segments(), frame_budget=600, fps=24)
    animated = [a.index for a in plan.assignments if a.assigned is Tier.ANIMATED]

    assert animated == [0]  # the 9-second title card, the only segment cheap enough
    critical = [
        i for i, (_, imp, _) in enumerate(SEVEN_MINUTE_OUTLINE) if imp == Importance.CRITICAL
    ]
    assert all(plan.tier_for(i) is Tier.REVEAL for i in critical)
    assert all(a.ideal is Tier.ANIMATED for a in plan.demoted)


def test_a_generous_budget_animates_nearly_every_segment() -> None:
    """T18A's actual product goal, pinned as a regression guard: the corrected budget must not
    quietly shrink back toward D16's original, wrong figure and reintroduce the slideshow.

    ASIDE-importance segments cap at Tier.REVEAL by design (IDEAL_TIER), never Tier.ANIMATED --
    that ceiling, not a budget shortfall, is why 2 of 15 never animate even with budget to
    spare. Every other segment, spanning every other importance level, does.
    """
    plan = resolve_tiers(seven_minute_segments(), frame_budget=10_500, fps=24)

    aside_count = sum(1 for _, imp, _ in SEVEN_MINUTE_OUTLINE if imp == Importance.ASIDE)
    assert plan.spread[Tier.STATIC] == 0
    assert plan.spread[Tier.REVEAL] == aside_count
    assert plan.spread[Tier.ANIMATED] == len(SEVEN_MINUTE_OUTLINE) - aside_count
    assert not plan.demoted, "budget to spare should leave nothing short of its ideal"


def test_an_unmeasured_segment_is_refused_rather_than_treated_as_free() -> None:
    """Invariant 1. Tier 2 costs duration x fps, so None must never read as zero."""
    segments = [a_segment(0), a_segment(1, duration_ms=None), a_segment(2, duration_ms=None)]

    with pytest.raises(ValueError, match=r"\[1, 2\].*duration_ms"):
        resolve_tiers(segments, frame_budget=600, fps=24)


def test_no_segments_is_an_empty_plan_not_an_error() -> None:
    plan = resolve_tiers([], frame_budget=600, fps=24)

    assert plan.assignments == ()
    assert plan.frames_used == 0
    assert plan.spread == dict.fromkeys(Tier, 0)


def test_a_zero_budget_leaves_every_segment_on_the_static_floor() -> None:
    """Tier 0 is never refused for cost -- a segment must render -- so frames_used overruns."""
    segments = [a_segment(i, Importance.CRITICAL) for i in range(4)]
    plan = resolve_tiers(segments, frame_budget=0, fps=24)

    assert plan.spread[Tier.STATIC] == 4
    assert plan.frames_used == 4 > plan.frame_budget
    assert all(a.demoted for a in plan.assignments)


def test_the_answer_does_not_depend_on_the_order_segments_arrive_in() -> None:
    """Ties break on index, so a shuffled input must give a byte-identical plan."""
    ordered = seven_minute_segments()
    shuffled = ordered[:]
    random.Random(0).shuffle(shuffled)

    assert resolve_tiers(shuffled, frame_budget=600, fps=24) == resolve_tiers(
        ordered, frame_budget=600, fps=24
    )


def test_every_visual_intent_declares_its_tier_support() -> None:
    """Mirrors the SLOT_SCHEMAS coverage test: an intent added to the enum and nowhere else
    would otherwise surface as a KeyError minutes into a job."""
    assert set(TIER_SUPPORT) == set(VisualIntent)
    assert all(Tier.STATIC in tiers for tiers in TIER_SUPPORT.values())


def test_a_reveal_is_refused_when_the_budget_binds_during_the_first_pass() -> None:
    """The pass-1 branch no realistic fixture reaches: a reveal that does not fit is skipped.

    Ten NORMAL segments cost 10 frames of static floor. Promotion is charged as the *step*
    from the tier already held, so each reveal costs 8 - 1 = 7 rather than 8. A budget of 34
    affords three of them (10 + 21 = 31; a fourth would reach 38) -- so seven segments are
    refused a promotion they are individually eligible for. Ties break on index, so the three
    winners are 0, 1 and 2.
    """
    segments = [a_segment(i) for i in range(10)]
    plan = resolve_tiers(segments, frame_budget=34, fps=24)

    assert plan.spread[Tier.REVEAL] == 3
    assert [a.index for a in plan.assignments if a.assigned is Tier.REVEAL] == [0, 1, 2]
    assert plan.frames_used == 31 <= plan.frame_budget


@pytest.mark.parametrize("fps", [0, -1, -24])
def test_a_non_positive_fps_is_refused(fps: int) -> None:
    """Tier 2 costs duration x fps. At fps 0 every animation is free and the budget is a lie."""
    with pytest.raises(ValueError, match="fps must be positive"):
        resolve_tiers([a_segment(0)], frame_budget=600, fps=fps)


def test_a_negative_frame_budget_is_refused() -> None:
    """Zero is legitimate -- it means 'everything static'. Negative is a caller bug."""
    with pytest.raises(ValueError, match="frame_budget cannot be negative"):
        resolve_tiers([a_segment(0)], frame_budget=-1, fps=24)


def test_duplicate_segment_indexes_are_refused_and_the_message_names_them() -> None:
    """Assignments are keyed by index, so a duplicate silently loses one segment's tier."""
    segments = [a_segment(0), a_segment(1), a_segment(1), a_segment(3), a_segment(3)]

    with pytest.raises(ValueError, match=r"duplicate segment indexes.*\[1, 3\]"):
        resolve_tiers(segments, frame_budget=600, fps=24)


def test_an_intent_that_cannot_render_statically_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unreachable today: TIER_SUPPORT gives every intent all three tiers (D36).

    T17 is the first code in a position to narrow it, and the day it does, an intent with no
    static form is a job that dies at render time -- the budget can put *any* segment on Tier 0.
    Reached by monkeypatching the map rather than by weakening the real one, so the guard is
    covered without the production default quietly becoming the test's default.
    """
    monkeypatch.setitem(TIER_SUPPORT, VisualIntent.TITLE_CARD, frozenset({Tier.ANIMATED}))
    aside = a_segment(0, Importance.ASIDE, intent=VisualIntent.TITLE_CARD)

    with pytest.raises(ValueError, match=r"omits Tier\.STATIC"):
        ideal_tier(aside)


def test_tier_for_raises_on_a_segment_that_was_never_planned() -> None:
    """A missing index is a caller bug, and a default return would render it as a Tier 0."""
    plan = resolve_tiers([a_segment(0), a_segment(1)], frame_budget=600, fps=24)

    assert plan.tier_for(1) is Tier.REVEAL
    with pytest.raises(KeyError, match="no tier assignment for segment index 7"):
        plan.tier_for(7)


def test_below_a_third_of_a_second_an_animation_costs_less_than_a_reveal() -> None:
    """A known inversion, pinned so a future reader files it as known rather than as a bug.

    Tier 1 is a flat 8 frames; Tier 2 is ceil(duration x fps). Below ~333ms at 24fps the
    ordering flips and a segment that lost the reveal pass can take an animation for less. The
    budget accounting stays correct throughout, and real narration never gets near this -- a
    floor is not added because it would make frame_cost lie about the cost model.
    """
    assert frame_cost(Tier.ANIMATED, 100, 24) == 3 < REVEAL_FRAME_COST
    assert frame_cost(Tier.ANIMATED, 1_000, 24) == 24 > REVEAL_FRAME_COST
    assert frame_cost(Tier.ANIMATED, 1, 24) == 1, "a rendered segment is never zero frames"
