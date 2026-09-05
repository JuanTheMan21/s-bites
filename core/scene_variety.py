"""Enforcing ``runtime_skills/visual-plan``'s own hard rules on the plan it actually returns,
in code -- the same move this project makes everywhere else a rule mattered enough to be an
invariant rather than a request (``scene_author`` taking ``duration_ms`` as a required parameter
so Invariant 1 is a type error, not a plea). The rules themselves are not new: the skill pack has
stated "no block type may lead more than a third of the video" and "consecutive segments must not
share a primary block type" since T18C. What is new is that a violation is now DETECTED, so
``core/graph/nodes/visual_plan.py`` can spend its one bounded re-ask on it, the same "corrective
appendix naming exactly what was wrong" shape ``core/block_triggers.py::missed_block_opportunities``
already established for the opposite problem (a type never used at all).

Pure and stdlib-only, like ``core/tier_resolver.py``/``core/block_triggers.py`` -- a decision
about a whole video's plan, made once, before anything is authored or rendered.
"""

import itertools

from core.block_types import BlockType
from core.scene_plan_schema import SegmentScenePlan, VideoScenePlan

# No block type may be the primary (first) block of more than a third of the video's segments --
# the skill pack's own stated rule, unenforced in code until now.
_MAX_TYPE_FRACTION = 1 / 3

# T18I: the user's own direct complaint, verbatim -- a sequence diagram "is used too much, in all
# videos", cool but overused. Tighter than the general cap: at most one in five segments (and
# always at least room for one), since even staying under the general 1/3 rule still let it lead
# most videos before this.
_MAX_SEQUENCE_DIAGRAM_FRACTION = 1 / 5

# T18J: found in a real render, not guessed -- 4 of 15 segments came back as `title` (segments 0,
# 4, 9, 11), and only segment 0 is the forced opener. The other three were regular content
# segments with real explanatory narration, rendered as a single static headline+paragraph with
# no progressive reveal -- exactly the user's own complaint ("this one can have some points
# appearing instead of this plain visual throughout"). `runtime_skills/visual-plan`'s own table
# already says `title` is for "the opening, or a genuine change of subject mid-video" and
# explicitly NOT for "any segment with real content" -- the model was not following its own
# stated rule, and nothing checked. A video may have at most one genuine subject-change moment
# per ~10 segments before this reads as the model reaching for `title` as a generic "just show
# the point" fallback rather than reserving it for what it is actually for.
_MAX_TITLE_FRACTION = 1 / 10


def _primary_type(plan: SegmentScenePlan) -> BlockType | None:
    return plan.blocks[0].block_type if plan.blocks else None


def check_variety(plan: VideoScenePlan) -> list[str]:
    """Human-readable violations of the plan's own stated variety rules, empty when it complies.

    Segment 0 is excluded throughout -- ``visual_plan.py`` overrides its plan with a forced title
    card regardless of what the model returns for it (``_forced_title_scene``), so a real
    violation can never involve it and counting it would only skew every fraction below.
    """
    by_index = {p.segment_index: p for p in plan.segments if p.segment_index != 0}
    if not by_index:
        return []
    ordered = [by_index[i] for i in sorted(by_index)]
    total = len(ordered)

    violations: list[str] = []

    counts: dict[BlockType, int] = {}
    for p in ordered:
        primary = _primary_type(p)
        if primary is not None:
            counts[primary] = counts.get(primary, 0) + 1

    for block_type, count in counts.items():
        # max(1, ...): a video with only one or two real segments cannot possibly keep any type
        # under a third of the total (1 of 1 is 100% no matter what it is) -- the floor gives
        # every video at least one "free" use of its own necessary type before this fires, the
        # same reasoning the sequence_diagram cap just below already applies explicitly.
        if count > max(1, total * _MAX_TYPE_FRACTION):
            violations.append(
                f"`{block_type.value}` is the primary block of {count} of {total} segments -- "
                "no single block type may lead more than a third of the video. Swap some of "
                "these for a different block type that also fits their narration."
            )

    sequence_count = counts.get(BlockType.SEQUENCE_DIAGRAM, 0)
    # No round() -- the same reasoning the general check above already uses raw-float for.
    # round() would silently loosen this cap for any total whose fractional part rounds up
    # (e.g. a 9-segment video: 2 of 9 is 22%, over the stated "one in five", but
    # round(9 * 0.2) == 2 would let it through). Caught live, not guessed: project-reviewer.
    if sequence_count > max(1, total * _MAX_SEQUENCE_DIAGRAM_FRACTION):
        violations.append(
            f"`sequence_diagram` is the primary block of {sequence_count} of {total} segments -- "
            "it reads as repetitive and is capped tighter than other types. Keep it only for the "
            "segment(s) where a back-and-forth exchange is genuinely the clearest way to explain "
            "the narration; give the rest a different block type."
        )

    title_count = counts.get(BlockType.TITLE, 0)
    if title_count > max(1, total * _MAX_TITLE_FRACTION):
        violations.append(
            f"`title` is the primary block of {title_count} of {total} non-opening segments -- "
            "title is for the opening or a genuine change of subject, never for a segment with "
            "real explanatory content (that content needs to actually appear, progressively, "
            "which title cannot do). Replace the extra title segments with text_panel, "
            "icon_panel, or whichever block actually fits what that segment explains."
        )

    for prev, curr in itertools.pairwise(ordered):
        # curr.segment_index == prev.segment_index + 1: a strict-mode plan is never guaranteed
        # to cover every index (visual_plan.py::_fallback_scene's own docstring, D74's
        # precedent) -- two segments this list places next to each other are not necessarily
        # adjacent in the real video if the model's plan skipped one in between. Caught by
        # project-reviewer: comparing list-adjacent segments regardless of index gap could flag
        # two segments as "back to back" with a real (fallback) segment sitting between them.
        if curr.continues_previous or curr.segment_index != prev.segment_index + 1:
            continue
        prev_type, curr_type = _primary_type(prev), _primary_type(curr)
        if prev_type is not None and prev_type == curr_type:
            violations.append(
                f"segments {prev.segment_index} and {curr.segment_index} both lead with "
                f"`{curr_type.value}` back to back, and segment {curr.segment_index} is not "
                "marked continues_previous -- give one of them a different block type, or set "
                "continues_previous if it is genuinely meant to pick up where the last one left "
                "off."
            )

    return violations
