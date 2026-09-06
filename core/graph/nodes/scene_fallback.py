"""The safe fallback a segment's render lands on once a re-authored scene (``scene_reauthor.py``)
still fails geometry validation, or the finding wasn't content-shaped to begin with (``rendering/
geometry_findings.py::is_content_retryable``).

T18I: per-segment isolation for the production failure story -- one bad segment used to kill the
whole ``VideoJob`` (``core/graph/nodes/render_scene.py``'s own exception propagating through the
graph). A plain title card is geometry-safe by construction (it is what every segment 0 already
renders, and TITLE is the simplest block in the library) and needs no LLM call, so it costs
nothing and cannot itself trigger the same failure -- a degraded segment is a title card, never a
hole in the finished video.
"""

import re

from core.block_schemas import TitleKeyTerm, TitleSlots
from core.block_types import BlockType, MotifName, SceneLayout
from core.models import Segment
from core.scene_schemas import ComposedBlock, ComposedScene

# T18M: `key_terms=[]` used to be hardcoded, leaving the fallback title card's chip-staging
# animation (`rendering/templates/_block_title.html`'s chip loop, T18G's F3) with nothing to
# stage -- a static wall of text held for 21-31s on a real render's four fallback segments. Every
# fragment below is copied VERBATIM out of the segment's own narration (no LLM call, so this
# still cannot fail the way the scene it replaces did) as both chip text and anchor_phrase, so
# `rendering/anchors.py::resolve_anchor`'s consecutive-word match can never fail to find it.
_SENTENCE_RE = re.compile(r"[^.!?]+[.!?]?")
_MAX_CHIPS = 4
_CHIP_WORDS = 4
_SUBTITLE_MAX_CHARS = 60


def _leading_fragment(sentence: str, *, words: int) -> str:
    return " ".join(sentence.split()[:words]).strip(" .,;:!?")


def _key_terms_from_narration(narration: str | None) -> list[TitleKeyTerm]:
    """Up to ``_MAX_CHIPS`` short leading fragments, one per sentence, each short enough that the
    card itself cannot overflow -- empty for a null or sentence-less narration, matching today's
    behavior rather than regressing it."""
    if not narration:
        return []
    terms = []
    for sentence in _SENTENCE_RE.findall(narration)[:_MAX_CHIPS]:
        fragment = _leading_fragment(sentence, words=_CHIP_WORDS)
        if fragment:
            terms.append(TitleKeyTerm(text=fragment, anchor_phrase=fragment))
    return terms


def _short_subtitle(summary: str) -> str:
    """``segment.summary`` truncated at a word boundary -- the full summary (166-198 chars on a
    real render's fallback segments) is what made the card a wall of text in the first place."""
    if len(summary) <= _SUBTITLE_MAX_CHARS:
        return summary
    return summary[:_SUBTITLE_MAX_CHARS].rsplit(" ", 1)[0]


def title_card_scene(segment: Segment, motif: MotifName) -> ComposedScene:
    """A single, geometry-safe TITLE block built deterministically from ``segment``'s own
    ``title``/``summary``/``narration`` -- no ``LLMProvider`` call, so this cannot itself fail
    the way the scene it is replacing did."""
    payload = TitleSlots(
        headline=segment.title,
        subtitle=_short_subtitle(segment.summary),
        key_terms=_key_terms_from_narration(segment.narration),
    )
    return ComposedScene(
        motif=motif,
        layout=SceneLayout.SINGLE,
        blocks=[
            ComposedBlock(
                block_type=BlockType.TITLE,
                role="Fallback content after a render failure",
                anchor_phrase=None,
                payload=payload.model_dump(),
            )
        ],
        continues_previous=False,
    )
