"""Believable ``Segment`` inputs, shared by every test that needs a plausible outline.

Not a test module. The same role ``tests/slot_examples.py`` plays for slot payloads: one
realistic fixture, defined once, used by whichever test needs it. T6 uses it for the tier
resolver; T16 will use it for the narrate-measure-tier stretch, which cares about exactly the
same shape of input.

Realistic rather than minimal, on purpose. A resolver fed three identical 28-second segments
answers a question nobody asked -- the interesting behaviour only appears when durations and
importances actually vary.
"""

from core import Importance, Segment, VisualIntent

# A plausible 7-minute explainer: ~412 seconds over 15 segments, importance spread across all
# five levels, and -- crucially -- a couple of genuinely short segments. A title card and a stat
# callout are short in real life, and at FRAME_BUDGET=600 they are the only things Tier 2 can
# afford. See test_the_budget_buys_shortness_not_importance.
SEVEN_MINUTE_OUTLINE: list[tuple[VisualIntent, Importance, int]] = [
    (VisualIntent.TITLE_CARD, Importance.MAJOR, 9),
    (VisualIntent.BULLET_LIST, Importance.NORMAL, 32),
    (VisualIntent.CODE_WALKTHROUGH, Importance.CRITICAL, 34),
    (VisualIntent.COMPARISON, Importance.MAJOR, 36),
    (VisualIntent.DIAGRAM_FLOW, Importance.CRITICAL, 38),
    (VisualIntent.BULLET_LIST, Importance.NORMAL, 33),
    (VisualIntent.STAT_CALLOUT, Importance.MAJOR, 12),
    (VisualIntent.BULLET_LIST, Importance.MINOR, 30),
    (VisualIntent.CODE_WALKTHROUGH, Importance.MAJOR, 36),
    (VisualIntent.BULLET_LIST, Importance.ASIDE, 26),
    (VisualIntent.COMPARISON, Importance.NORMAL, 34),
    (VisualIntent.DIAGRAM_FLOW, Importance.NORMAL, 32),
    (VisualIntent.STAT_CALLOUT, Importance.MINOR, 14),
    (VisualIntent.BULLET_LIST, Importance.NORMAL, 35),
    (VisualIntent.TITLE_CARD, Importance.ASIDE, 11),
]


def a_segment(
    index: int,
    importance: Importance = Importance.NORMAL,
    duration_ms: int | None = 28_000,
    intent: VisualIntent = VisualIntent.BULLET_LIST,
) -> Segment:
    """One measured segment. ``duration_ms=None`` gives the *unmeasured* case Invariant 1 bans."""
    return Segment(
        index=index,
        title=f"Segment {index}",
        summary="One idea, explained.",
        visual_intent=intent,
        importance=importance,
        narration="Narration.",
        duration_ms=duration_ms,
    )


def seven_minute_segments() -> list[Segment]:
    """SEVEN_MINUTE_OUTLINE as measured segments, indexed from 0."""
    return [
        a_segment(i, importance, seconds * 1000, intent)
        for i, (intent, importance, seconds) in enumerate(SEVEN_MINUTE_OUTLINE)
    ]
