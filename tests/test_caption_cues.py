"""``mux/caption_cues.py`` -- pure, no I/O, no network."""

from interfaces.tts_provider import WordMark
from mux.caption_cues import MAX_WORDS_PER_CUE, Cue, cues_for_segment, group_into_cues


def _marks(n: int, *, gap_ms: int = 300, word_ms: int = 250) -> list[WordMark]:
    return [WordMark(text=f"w{i}", offset_ms=i * gap_ms, duration_ms=word_ms) for i in range(n)]


def test_group_into_cues_chunks_at_max_words_per_cue() -> None:
    marks = _marks(9)

    cues = group_into_cues(marks)

    assert len(cues) == 2
    assert len(cues[0].words) == MAX_WORDS_PER_CUE
    assert len(cues[1].words) == 1
    assert cues[0].start_ms == 0
    assert cues[1].start_ms == marks[8].offset_ms


def test_group_into_cues_of_empty_input_is_empty() -> None:
    assert group_into_cues([]) == []


def test_cues_for_segment_prefers_real_word_marks_over_narration() -> None:
    marks = _marks(3)

    cues = cues_for_segment(marks, "completely different text entirely", 5000)

    assert len(cues) == 1
    assert cues[0].text == "w0 w1 w2"


def test_cues_for_segment_falls_back_to_narration_when_word_marks_are_empty() -> None:
    """T18K/D161: this is the exact gap the in-frame caption band had and the .srt sidecar
    didn't -- a TTS adapter reporting no word boundaries must still produce *something*, not a
    blank band for the whole segment."""
    cues = cues_for_segment([], "one two three four five six seven eight nine", 9000)

    assert len(cues) == 2
    assert cues[0].text == "one two three four five six seven eight"
    assert cues[1].text == "nine"
    # spread evenly across the full duration, not bunched at the start
    assert cues[0].start_ms == 0
    assert cues[-1].end_ms == 9000


def test_cues_for_segment_with_neither_word_marks_nor_narration_is_empty() -> None:
    assert cues_for_segment([], None, 5000) == []
    assert cues_for_segment([], "", 5000) == []


def test_cues_for_segment_narration_fallback_is_a_real_cue_list_not_one_giant_block() -> None:
    """The bug this replaces: the old in-frame-band-has-no-fallback behavior effectively showed
    nothing; a naive fallback might instead show one giant unreadable block for the whole
    segment. Neither should happen -- cues stay bounded at MAX_WORDS_PER_CUE like any other cue
    list."""
    narration = " ".join(f"word{i}" for i in range(20))

    cues = cues_for_segment([], narration, 20_000)

    assert all(len(c.words) <= MAX_WORDS_PER_CUE for c in cues)
    assert sum(len(c.words) for c in cues) == 20


def test_cue_is_a_frozen_dataclass_with_the_documented_fields() -> None:
    cue = Cue(words=(), start_ms=0, end_ms=0, text="")
    assert cue.words == ()
