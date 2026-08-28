"""Scheduling a scene's motion against the words that are actually being said.

T18A shipped real per-word timing (``interfaces/tts_provider.py::WordMark``) and it fed only
captions -- every other tween in every template ran on a fixed, hand-picked timeline offset,
unrelated to the narration. T18B spends that measurement on the visuals too: a block's entrance,
or one array cell's elimination, can now land on the exact word that describes it rather than an
arbitrary beat.

Pure and testable, no I/O: given a segment's ``word_marks`` and a phrase or a list of item
strings, find where in the audio that text is actually said. Degradation is mandatory, not
optional -- ``SynthesisResult.words`` "may be empty" is an explicit contract term, and a phrase
may simply not match (paraphrased narration, a word the LLM's plan quoted loosely). Every caller
must treat ``None`` as "no anchor found, fall back to your own default timing" rather than as an
error.
"""

import re

from interfaces.tts_provider import WordMark

_WORD_RE = re.compile(r"[a-z0-9]+")


def _normalize(text: str) -> list[str]:
    """Lowercase, strip punctuation, split on whitespace -- so 'discarded.' matches 'discarded'
    and a phrase's exact casing or trailing punctuation never blocks a match."""
    return _WORD_RE.findall(text.lower())


def resolve_anchor(word_marks: list[WordMark], phrase: str | None) -> int | None:
    """The ``offset_ms`` of ``phrase``'s first word within ``word_marks``, or ``None`` if
    ``phrase`` is empty, ``word_marks`` is empty, or no run of consecutive words matches it.

    Matching is a normalized substring search over the word sequence: ``phrase``'s words must
    appear consecutively and in order, tolerant of case and punctuation, but not tolerant of
    words in between -- a loose "contains all these words somewhere" match would as often find
    the wrong moment as the right one.
    """
    if not phrase or not word_marks:
        return None

    needle = _normalize(phrase)
    if not needle:
        return None

    haystack = [_normalize(word.text) for word in word_marks]
    needle_len = len(needle)
    for start in range(len(haystack) - needle_len + 1):
        if all(
            haystack[start + i] and haystack[start + i][0] == needle[i] for i in range(needle_len)
        ):
            return word_marks[start].offset_ms
    return None


def derive_item_anchors(word_marks: list[WordMark], items: list[str]) -> list[int | None]:
    """One anchor per item in ``items``, matched against ``word_marks`` independently.

    For a list already on screen (bullets, chain node labels, array cell contents) this needs no
    LLM call and no schema field -- an item's own text is already the thing being said, so its
    anchor is just where that text occurs in the narration. Returns one entry per ``items``
    element, in the same order, each possibly ``None``.
    """
    return [resolve_anchor(word_marks, item) for item in items]
