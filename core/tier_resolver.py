"""Which segments get rendered richly, and which settle for a single frame.

Importance says what a segment *deserves*; the frame budget says what we can *afford*. The
difference between the two is a demotion, and keeping both on the result is what lets ``/tiers``
report "demoted from Tier 2" rather than an unexplained Tier 1.

Imports stdlib and ``core.models``, and nothing else, ever. No clock, no filesystem, no config:
the budget and the frame rate arrive as parameters precisely so this module never learns that
``FRAME_BUDGET`` and ``FPS`` exist. It is the one module in the system with no excuse for a
dependency, which is also what makes it exhaustively testable in T6.

Frame costs per tier come from the ``scene-templates`` skill. Tier 2 is the only one that varies,
and it varies with *measured* audio -- so this cannot run before narration has been synthesised,
and it says so loudly rather than treating an unmeasured segment as free.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass

from core.models import Importance, Segment, Tier, VisualIntent

# Per the scene-templates skill: Tier 0 is one screenshot held for the audio duration, Tier 1 is
# 3-5 screenshots of different reveal states crossfaded by ffmpeg. Tier 2 has no constant here
# because its cost is a function of the measured narration.
STATIC_FRAME_COST = 1
REVEAL_FRAME_COST = 8

# What a segment wants, before the budget has its say. Importance is the outline model's
# judgement of what matters; this ladder turns that judgement into a rendering ambition. Two
# importances aim at Tier 2 rather than one so the budget genuinely binds -- with a single
# candidate the resolver would have nothing to choose between and demotion would never happen.
# T18A: NORMAL/MINOR moved up to Tier.ANIMATED -- the old ladder was tuned against D16's since-
# corrected throughput figure. Animation is now the default; only ASIDE settles for Tier.REVEAL.
IDEAL_TIER: dict[Importance, Tier] = {
    Importance.CRITICAL: Tier.ANIMATED,
    Importance.MAJOR: Tier.ANIMATED,
    Importance.NORMAL: Tier.ANIMATED,
    Importance.MINOR: Tier.ANIMATED,
    Importance.ASIDE: Tier.REVEAL,
}

ALL_TIERS = frozenset(Tier)

# The registration point /newintent step 5 names. Every intent supports every tier today, so
# this is a no-op -- it exists so that T17, which writes the templates and is the first code in
# a position to know, has somewhere to record an intent with no meaningful reveal form. Spelled
# out member by member rather than comprehended: a comprehension cannot go stale, but neither
# can it be the line someone adds a new intent to.
TIER_SUPPORT: dict[VisualIntent, frozenset[Tier]] = {
    VisualIntent.TITLE_CARD: ALL_TIERS,
    VisualIntent.BULLET_LIST: ALL_TIERS,
    VisualIntent.COMPARISON: ALL_TIERS,
    VisualIntent.DIAGRAM_FLOW: ALL_TIERS,
    VisualIntent.CODE_WALKTHROUGH: ALL_TIERS,
    VisualIntent.STAT_CALLOUT: ALL_TIERS,
}


@dataclass(frozen=True, slots=True)
class TierAssignment:
    """One segment's tier, the tier it wanted, and what that costs to render."""

    index: int
    ideal: Tier
    assigned: Tier
    frame_cost: int

    @property
    def demoted(self) -> bool:
        """True when the budget, not the segment's own importance, decided its tier."""
        return self.assigned < self.ideal


@dataclass(frozen=True, slots=True)
class TierPlan:
    """Every assignment for one job, in segment order, and what they spent between them."""

    assignments: tuple[TierAssignment, ...]
    frame_budget: int

    @property
    def frames_used(self) -> int:
        """May exceed ``frame_budget``: Tier 0 is a floor and is never refused for cost."""
        return sum(a.frame_cost for a in self.assignments)

    @property
    def spread(self) -> dict[Tier, int]:
        """How many segments landed on each tier.

        Every tier is keyed, zeros included, so a caller asking "did all three appear" reads a
        0 rather than catching a ``KeyError``.
        """
        counts = dict.fromkeys(Tier, 0)
        for assignment in self.assignments:
            counts[assignment.assigned] += 1
        return counts

    @property
    def demoted(self) -> tuple[TierAssignment, ...]:
        """The segments the budget cut down, for ``/tiers`` to report."""
        return tuple(a for a in self.assignments if a.demoted)

    def tier_for(self, index: int) -> Tier:
        """The tier assigned to one segment. Raises ``KeyError`` if it was never planned."""
        for assignment in self.assignments:
            if assignment.index == index:
                return assignment.assigned
        raise KeyError(f"no tier assignment for segment index {index}")


def frame_cost(tier: Tier, duration_ms: int, fps: int) -> int:
    """What rendering a segment at ``tier`` costs in frames. The one definition of the model."""
    if tier is Tier.STATIC:
        return STATIC_FRAME_COST
    if tier is Tier.REVEAL:
        return REVEAL_FRAME_COST
    return max(1, math.ceil(duration_ms / 1000 * fps))


def ideal_tier(segment: Segment) -> Tier:
    """The richest tier this segment's importance asks for and its visual intent can carry."""
    wanted = IDEAL_TIER[segment.importance]
    candidates = [tier for tier in TIER_SUPPORT[segment.visual_intent] if tier <= wanted]
    if not candidates:
        raise ValueError(
            f"TIER_SUPPORT[{segment.visual_intent}] omits Tier.STATIC. Every intent needs a "
            "static form -- the budget can put any segment on Tier 0."
        )
    return max(candidates)


def resolve_tiers(segments: Sequence[Segment], *, frame_budget: int, fps: int) -> TierPlan:
    """Assign every segment a tier: ambition from importance, ceiling from the frame budget.

    Everyone starts on Tier 0 -- unconditionally, since a segment must render -- and is then
    promoted toward its ideal in importance order, ties broken by index. Reveals are seeded in a
    first pass and animations in a second: one combined pass by importance lets a single long,
    important segment spend the entire budget before anything else gets even a reveal, which is
    precisely the single-tier outcome D9 calls a decorative tier system.

    Budget-greedy per D9 -- a candidate that does not fit is skipped rather than ending the
    pass, because a shorter one further down the order may still fit.

    Raises:
        ValueError: on an unmeasured segment (Invariant 1: tier assignment cannot precede
            narration), a non-positive ``fps``, a negative ``frame_budget``, or duplicate
            segment indexes.
    """
    _validate(segments, frame_budget=frame_budget, fps=fps)

    ideals = {segment.index: ideal_tier(segment) for segment in segments}
    assigned = dict.fromkeys(ideals, Tier.STATIC)
    spent = len(segments) * STATIC_FRAME_COST
    order = sorted(segments, key=lambda s: (-s.importance, s.index))

    for target in (Tier.REVEAL, Tier.ANIMATED):
        for segment in order:
            if ideals[segment.index] < target:
                continue
            current = assigned[segment.index]
            step = frame_cost(target, segment.duration_ms, fps) - frame_cost(
                current, segment.duration_ms, fps
            )
            if spent + step <= frame_budget:
                assigned[segment.index] = target
                spent += step

    return TierPlan(
        assignments=tuple(
            TierAssignment(
                index=segment.index,
                ideal=ideals[segment.index],
                assigned=assigned[segment.index],
                frame_cost=frame_cost(assigned[segment.index], segment.duration_ms, fps),
            )
            for segment in sorted(segments, key=lambda s: s.index)
        ),
        frame_budget=frame_budget,
    )


def _validate(segments: Sequence[Segment], *, frame_budget: int, fps: int) -> None:
    if fps <= 0:
        raise ValueError(f"fps must be positive, got {fps}")
    if frame_budget < 0:
        raise ValueError(f"frame_budget cannot be negative, got {frame_budget}")

    indexes = [segment.index for segment in segments]
    duplicates = sorted({i for i in indexes if indexes.count(i) > 1})
    if duplicates:
        raise ValueError(f"duplicate segment indexes, so a tier would be ambiguous: {duplicates}")

    unmeasured = sorted(s.index for s in segments if s.duration_ms is None)
    if unmeasured:
        raise ValueError(
            f"segments {unmeasured} have no measured duration_ms. Tier assignment runs *after* "
            "narration is synthesised and measured (Invariant 1) -- Tier 2 costs duration x "
            "fps, so an unmeasured segment looks free and spends the budget on nothing."
        )
