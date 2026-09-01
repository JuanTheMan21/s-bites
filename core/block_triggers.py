"""A small trigger vocabulary per block type, and the scan that flags when a segment's own
narration clearly calls for a block the video's plan never used anywhere.

T18D's real-render matrix found this is a real gap, not a hypothetical one: 3 of 6 topics never
got the block type they were chosen to stress, and TIMELINE rendered zero times across the whole
matrix (``t18d_catalog.md``). ``core/graph/nodes/visual_plan.py`` uses this to decide whether a
single bounded re-ask is worth making.

T18G, D122 finding 2: the vocabulary scan alone has a real, confirmed blind spot -- a narration
that signals chronology entirely through domain-specific version numbers ("HTTP 1.0... HTTP
1.1... HTTP/2... HTTP/3...") never hits ``TRIGGER_VOCABULARY[BlockType.TIMELINE]``'s generic
words, however many of them there are, because none of those words are actually used.
``_looks_chronological`` is a second, independent signal for TIMELINE specifically: three or
more distinct version/sequence-like tokens ("1.0", "v2", "3/4") is itself evidence of a
chronological progression, regardless of vocabulary.

Pure -- stdlib and ``core.block_types``/``core.models``/``core.scene_plan_schema`` only, no I/O,
so this is safe to import and unit-test the same way ``core/tier_resolver.py`` is.
"""

import re

from core.block_types import BlockType
from core.models import Segment
from core.scene_plan_schema import VideoScenePlan

# A version-like token, three shapes: a dotted number ("1.0", "3.2.1"); a bare number directly
# after a slash with no space ("HTTP/2", "HTTP/3" -- the exact real-render shape D122 found,
# where the leading word is not itself a digit so a plain \d+(?:[./]\d+)+ pattern never matches);
# or a "v"-prefixed number ("v2", "v1.5").
_VERSION_TOKEN = re.compile(r"\d+\.\d+(?:\.\d+)?|(?<=/)\d+(?:\.\d+)?|\bv\d+(?:\.\d+)?\b")
_MIN_VERSION_TOKENS = 3


def _looks_chronological(text: str) -> bool:
    """Three or more DISTINCT version-like tokens is itself a chronology signal, independent of
    ``TRIGGER_VOCABULARY`` -- the exact blind spot D122 recorded: "HTTP 1.0... HTTP 1.1...
    HTTP/2... HTTP/3..." never uses a generic timeline word, but the version progression alone
    is unmistakably chronological to a human reader."""
    return len(set(_VERSION_TOKEN.findall(text))) >= _MIN_VERSION_TOKENS


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
        if BlockType.TIMELINE not in used and _looks_chronological(text):
            missed[segment.index] = BlockType.TIMELINE
            continue
        for block_type, vocabulary in TRIGGER_VOCABULARY.items():
            if block_type in used:
                continue
            hits = sum(1 for phrase in vocabulary if phrase in text)
            if hits >= _MIN_HITS:
                missed[segment.index] = block_type
                break
    return missed
