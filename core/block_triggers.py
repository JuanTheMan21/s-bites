"""A small trigger vocabulary per block type, and the scan that flags when a segment's own
narration clearly calls for a block the video's plan never used anywhere.

T18D's real-render matrix found this is a real gap, not a hypothetical one: 3 of 6 topics never
got the block type they were chosen to stress, and TIMELINE rendered zero times across the whole
matrix (``t18d_catalog.md``). ``core/graph/nodes/visual_plan.py`` uses this to decide whether a
single bounded re-ask is worth making.

Pure -- stdlib and ``core.block_types``/``core.models``/``core.scene_plan_schema`` only, no I/O,
so this is safe to import and unit-test the same way ``core/tier_resolver.py`` is.
"""

from core.block_types import BlockType
from core.models import Segment
from core.scene_plan_schema import VideoScenePlan

# A block type absent here has no distinctive narration vocabulary worth scanning for -- title,
# stat_callout, code_panel, text_panel, and graph_diagram all earn their place from structure or
# a general "this is the main content" judgment a keyword scan can't usefully approximate.
TRIGGER_VOCABULARY: dict[BlockType, frozenset[str]] = {
    BlockType.TIMELINE: frozenset(
        {
            "timeline",
            "chronological",
            "over the years",
            "then in",
            "later,",
            "history of",
            "evolved",
            "milestone",
            "decade",
        }
    ),
    BlockType.ARRAY_GRID: frozenset(
        {
            "sliding window",
            "binary search",
            "stack",
            "queue",
            "push",
            "pop",
            "shift the",
            "narrow the range",
            "enqueue",
            "dequeue",
        }
    ),
    BlockType.SEQUENCE_DIAGRAM: frozenset(
        {"request", "response", "handshake", "replies", "sends a", "round trip", "protocol"}
    ),
    BlockType.CODE_DIFF: frozenset(
        {"before and after", "the patch", "the fix", "vulnerable line", "refactor"}
    ),
}

# A segment's narration must hit at least this many distinct trigger phrases for one block type
# before the scan treats it as a real signal -- a single generic word ("request") is common
# enough in ordinary narration to be a false positive on its own.
_MIN_HITS = 2


def missed_block_opportunities(
    segments: list[Segment], plan: VideoScenePlan
) -> dict[int, BlockType]:
    """Segment index -> a block type its own narration clearly calls for, that no segment in
    ``plan`` uses anywhere in the video. Empty when nothing stands out."""
    used = {b.block_type for s in plan.segments for b in s.blocks}
    planned_indices = {s.segment_index for s in plan.segments}

    missed: dict[int, BlockType] = {}
    for segment in segments:
        if segment.index == 0 or segment.index not in planned_indices or not segment.narration:
            continue
        text = segment.narration.lower()
        for block_type, vocabulary in TRIGGER_VOCABULARY.items():
            if block_type in used:
                continue
            hits = sum(1 for phrase in vocabulary if phrase in text)
            if hits >= _MIN_HITS:
                missed[segment.index] = block_type
                break
    return missed
