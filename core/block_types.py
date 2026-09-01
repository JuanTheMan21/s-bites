"""The compositional vocabulary: what a scene is built from, and how a scene is laid out.

T18B replaces "one ``VisualIntent`` picks one whole-scene template"
(``rendering/compose.py``, pre-T18B) with "one video's worth of segments are laid out and
composed from a small library of blocks" (``core/graph/nodes/visual_plan.py``). ``VisualIntent``
(``core/models.py``) is unchanged and still chosen at outline time -- it survives here only as a
coarse hint ``ALLOWED_BLOCKS`` documents, not as a rendering dispatch key.

T18C broadens the library: ``DIAGRAM_CHAIN`` is retired in favor of ``GRAPH_DIAGRAM`` (which
absorbs the old linear-rail case as one of its two layout modes, plus real arbitrary-topology
graphs); ``CODE_DIFF``, ``SEQUENCE_DIAGRAM``, and ``TIMELINE`` are new; ``ARRAY_GRID`` gains an
orientation and a generalized step model (narrow/shift/push/pop, not just narrowing). Annotations
(``AnnotationType``) are a new, separate cross-cutting overlay concept, not a ``BlockType`` --
they target a specific element inside an already-planned block rather than filling their own
``SceneLayout`` region, so they live in ``core/scene_plan_schema.py``/``core/scene_schemas.py``,
not the per-block registration list below.

Kept out of ``core/models.py`` on purpose: ``ALLOWED_BLOCKS`` needs ``VisualIntent``, so this
module depends on ``core.models`` one-way. Putting ``BlockType``/``SceneLayout``/``MotifName``
in ``models.py`` instead would need nothing back from here, but ``Segment.scene`` stays an
untyped dict either way (D29's pattern) -- there is no cycle to avoid by moving them, only a
module to keep smaller.
"""

from enum import StrEnum

from core.models import VisualIntent


class BlockType(StrEnum):
    """What a block *is*. Ten as of T18G -- ``ICON_PANEL`` is new, an abstract/generated-graphics
    block (inline SVG icon + label chips) for topic-appropriate visual variety, deliberately NOT
    a real photo/logo block (that needs a whole new interfaces/adapter pair, out of scope here)."""

    TITLE = "title"
    TEXT_PANEL = "text_panel"
    STAT_CALLOUT = "stat_callout"
    CODE_PANEL = "code_panel"
    ARRAY_GRID = "array_grid"
    GRAPH_DIAGRAM = "graph_diagram"
    CODE_DIFF = "code_diff"
    SEQUENCE_DIAGRAM = "sequence_diagram"
    TIMELINE = "timeline"
    ICON_PANEL = "icon_panel"


class SceneLayout(StrEnum):
    """How a segment's blocks are arranged in the frame. Two this task, both with a real
    template behind them (``rendering/templates/_layout_*.html``) -- a third (stacked) is real,
    cheap future work once a task needs it, not built speculatively now."""

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


class GraphLayoutMode(StrEnum):
    """``GRAPH_DIAGRAM``'s two rendering modes. ``CHAIN`` reproduces the retired
    ``DIAGRAM_CHAIN``'s single straight rail exactly; ``GRAPH`` places nodes on a real 2D canvas
    for arbitrary topology, with an optional traversal highlight."""

    CHAIN = "chain"
    GRAPH = "graph"


class ArrayOrientation(StrEnum):
    """``ARRAY_GRID``'s layout axis -- horizontal for most arrays/lists, vertical when the
    content reads more naturally as a stack."""

    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"


class ArrayStepOp(StrEnum):
    """What one ``ArrayStep`` does to the active range. ``NARROW`` shrinks it without
    translating (a binary search's halving); ``SHIFT`` translates it by its own width (a sliding
    window); ``PUSH``/``POP`` grow/shrink it by exactly one cell at its acting end (a stack or
    queue operation)."""

    NARROW = "narrow"
    SHIFT = "shift"
    PUSH = "push"
    POP = "pop"


class EndMarker(StrEnum):
    """An optional iconography badge at an ``ArrayStep``'s acting end."""

    NONE = "none"
    PLUS = "plus"
    MINUS = "minus"


class CodeDiffOp(StrEnum):
    """What one ``CodeDiffLine`` is: unchanged context, an added line, or a removed line."""

    CONTEXT = "context"
    ADD = "add"
    REMOVE = "remove"


class IconName(StrEnum):
    """``ICON_PANEL``'s closed icon vocabulary -- inline SVG paths hand-authored in
    ``rendering/templates/_block_icon_panel.html``, not a free-text choice, so every value here
    is guaranteed to have a real glyph to render. Generic enough to span most explainer topics
    (security, systems, data, general concepts) without needing a per-topic icon set."""

    LOCK = "lock"
    KEY = "key"
    SHIELD = "shield"
    CHECK = "check"
    NETWORK = "network"
    SERVER = "server"
    DATABASE = "database"
    WARNING = "warning"
    ARROW = "arrow"
    CLOCK = "clock"
    USER = "user"
    GLOBE = "globe"
    CODE = "code"
    GEAR = "gear"
    CHART = "chart"
    FLAG = "flag"


class AnnotationType(StrEnum):
    """What a cross-cutting overlay annotation is. Not a ``BlockType`` -- an annotation targets
    an element inside an already-planned block rather than filling its own layout region."""

    CURSOR = "cursor"
    CHECK = "check"
    WARNING = "warning"


# What each VisualIntent's segment can plausibly become, once plan_visuals looks at the actual
# narration rather than just the outline-time label. Deliberately generous, not a hard dispatch
# table: strict-schema structured output has no way to make a per-item enum conditional on
# another field (D29), so this is never enforced on the LLM's response -- it feeds
# runtime_skills/visual-plan/<version>.md's guidance table and a coverage test (every VisualIntent
# has at least one plausible block), the same "no-op registration point, spelled out member by
# member" role TIER_SUPPORT plays in core/tier_resolver.py.
ALLOWED_BLOCKS: dict[VisualIntent, frozenset[BlockType]] = {
    VisualIntent.TITLE_CARD: frozenset({BlockType.TITLE}),
    VisualIntent.BULLET_LIST: frozenset(
        {
            BlockType.TEXT_PANEL,
            BlockType.ARRAY_GRID,
            BlockType.GRAPH_DIAGRAM,
            BlockType.TIMELINE,
            BlockType.ICON_PANEL,
        }
    ),
    VisualIntent.COMPARISON: frozenset({BlockType.TEXT_PANEL, BlockType.CODE_DIFF}),
    VisualIntent.DIAGRAM_FLOW: frozenset(
        {
            BlockType.GRAPH_DIAGRAM,
            BlockType.ARRAY_GRID,
            BlockType.SEQUENCE_DIAGRAM,
            BlockType.TIMELINE,
            BlockType.ICON_PANEL,
        }
    ),
    VisualIntent.CODE_WALKTHROUGH: frozenset({BlockType.CODE_PANEL, BlockType.CODE_DIFF}),
    VisualIntent.STAT_CALLOUT: frozenset({BlockType.STAT_CALLOUT}),
}
