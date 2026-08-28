"""The compositional vocabulary: what a scene is built from, and how a scene is laid out.

T18B replaces "one ``VisualIntent`` picks one whole-scene template"
(``rendering/compose.py``, pre-T18B) with "one video's worth of segments are laid out and
composed from a small library of blocks" (``core/graph/nodes/visual_plan.py``). ``VisualIntent``
(``core/models.py``) is unchanged and still chosen at outline time -- it survives here only as a
coarse hint ``ALLOWED_BLOCKS`` documents, not as a rendering dispatch key.

Kept out of ``core/models.py`` on purpose: ``ALLOWED_BLOCKS`` needs ``VisualIntent``, so this
module depends on ``core.models`` one-way. Putting ``BlockType``/``SceneLayout``/``MotifName``
in ``models.py`` instead would need nothing back from here, but ``Segment.scene`` stays an
untyped dict either way (D29's pattern) -- there is no cycle to avoid by moving them, only a
module to keep smaller.
"""

from enum import StrEnum

from core.models import VisualIntent


class BlockType(StrEnum):
    """What a block *is*. Six this task -- direct lifts of five working templates plus one
    genuinely new one (``ARRAY_GRID``, T18B's own proof that the new mechanism carries a visual
    the old one structurally could not). More arrive in T18C without touching this module's
    shape."""

    TITLE = "title"
    TEXT_PANEL = "text_panel"
    STAT_CALLOUT = "stat_callout"
    CODE_PANEL = "code_panel"
    DIAGRAM_CHAIN = "diagram_chain"
    ARRAY_GRID = "array_grid"


class SceneLayout(StrEnum):
    """How a segment's blocks are arranged in the frame. Two this task, both with a real
    template behind them (``rendering/templates/_layout_*.html``) -- a third (stacked) is real,
    cheap future work once T18C needs it, not built speculatively now."""

    SINGLE = "single"
    SPLIT_HORIZONTAL = "split_horizontal"


class MotifName(StrEnum):
    """One per video, chosen once by ``core/graph/nodes/visual_plan.py``. Threads through
    ``rendering/palettes.py`` (which family of colors) and is carried on every
    ``core.scene_schemas.ComposedScene`` this video produces, so a per-segment render has it
    without needing the whole job."""

    BLUEPRINT = "blueprint"
    TERMINAL = "terminal"
    BROADCAST = "broadcast"


# What each VisualIntent's segment can plausibly become, once plan_visuals looks at the actual
# narration rather than just the outline-time label. Deliberately generous, not a hard dispatch
# table: strict-schema structured output has no way to make a per-item enum conditional on
# another field (D29), so this is never enforced on the LLM's response -- it feeds
# runtime_skills/visual-plan/1.0.md's guidance table and a coverage test
# (every VisualIntent has at least one plausible block), the same "no-op registration point,
# spelled out member by member" role TIER_SUPPORT plays in core/tier_resolver.py.
# BULLET_LIST and DIAGRAM_FLOW both widen toward ARRAY_GRID/DIAGRAM_CHAIN on purpose -- a
# segment outlined as an ordinary list or process is exactly the kind that turns out, once the
# narration is in hand, to actually be a sequence with structure (a binary search's halving, an
# attack chain) that a plain list of bullets cannot show.
ALLOWED_BLOCKS: dict[VisualIntent, frozenset[BlockType]] = {
    VisualIntent.TITLE_CARD: frozenset({BlockType.TITLE}),
    VisualIntent.BULLET_LIST: frozenset(
        {BlockType.TEXT_PANEL, BlockType.ARRAY_GRID, BlockType.DIAGRAM_CHAIN}
    ),
    VisualIntent.COMPARISON: frozenset({BlockType.TEXT_PANEL}),
    VisualIntent.DIAGRAM_FLOW: frozenset({BlockType.DIAGRAM_CHAIN, BlockType.ARRAY_GRID}),
    VisualIntent.CODE_WALKTHROUGH: frozenset({BlockType.CODE_PANEL}),
    VisualIntent.STAT_CALLOUT: frozenset({BlockType.STAT_CALLOUT}),
}
