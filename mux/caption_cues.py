"""Grouping a segment's ``word_marks`` into movie-style caption cues -- shared by
``mux/subtitles.py`` (the ``.srt`` sidecar) and ``rendering/templates/_captions.html`` (the
in-frame band), so the two never drift into disagreeing about where one cue ends and the next
begins. Before T18B each maintained its own grouping; the in-frame band had none at all and
simply inked every word on with nothing ever clearing, which is why it grew into a wall of text.
"""

from dataclasses import dataclass

from interfaces.tts_provider import WordMark

# A cue reads as one glance rather than a scrolling wall of text -- the same "nothing on screen
# is read twice" reasoning scene-authoring.md already applies to slot text.
MAX_WORDS_PER_CUE = 8


@dataclass(frozen=True, slots=True)
class Cue:
    """One caption cue: the words it holds, and when it starts and ends within its segment's
    own narration audio (``offset_ms``, same reference frame as ``WordMark`` -- relative to the
    start of *this segment's* audio, not the final concatenated video)."""

    words: tuple[WordMark, ...]
    start_ms: int
    end_ms: int
    text: str


def group_into_cues(word_marks: list[WordMark]) -> list[Cue]:
    """Group ``word_marks`` into cues of at most ``MAX_WORDS_PER_CUE`` words each, in order.

    Returns an empty list for empty input -- callers degrade to their own even-stagger fallback,
    the same rule every other ``word_marks``-may-be-empty consumer in this project follows.
    """
    cues = []
    for start in range(0, len(word_marks), MAX_WORDS_PER_CUE):
        group = tuple(word_marks[start : start + MAX_WORDS_PER_CUE])
        cues.append(
            Cue(
                words=group,
                start_ms=group[0].offset_ms,
                end_ms=group[-1].offset_ms + group[-1].duration_ms,
                text=" ".join(word.text for word in group),
            )
        )
    return cues


def _even_stagger_word_marks(narration: str, duration_ms: int) -> list[WordMark]:
    """Fabricate ``WordMark``s spread evenly across ``duration_ms`` -- the fallback every other
    word-timed consumer already uses (``mux/subtitles.py``'s pre-T18K ``elif segment.narration``
    branch) when a TTS adapter reports no word boundaries. Kept private: a caller with real
    ``word_marks`` should never see fabricated ones."""
    words = narration.split()
    if not words or duration_ms <= 0:
        return []
    slot_ms = duration_ms / len(words)
    return [
        WordMark(text=word, offset_ms=round(i * slot_ms), duration_ms=round(slot_ms))
        for i, word in enumerate(words)
    ]


def cues_for_segment(
    word_marks: list[WordMark], narration: str | None, duration_ms: int
) -> list[Cue]:
    """The one grouping every caption consumer should call, in-frame band included (T18K --
    D161 traced the in-frame band's blank-on-empty-``word_marks`` behavior to this exact gap).

    Real ``word_marks`` win when present. Failing that, a non-empty ``narration`` is spread
    evenly across ``duration_ms`` and grouped the same way -- the same degrade-to-something-usable
    rule ``mux/subtitles.py`` has followed since T18B, now shared rather than duplicated. Only
    truly empty input (no marks, no narration) returns ``[]``.
    """
    if word_marks:
        return group_into_cues(word_marks)
    if narration:
        return group_into_cues(_even_stagger_word_marks(narration, duration_ms))
    return []
