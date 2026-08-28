"""Writing ``final.srt`` beside ``final.mp4`` -- the sidecar the terminal entrypoint (T18A)
prints alongside the video, and a fallback for any player that does not render the in-frame
caption band ``rendering/templates/_captions.html`` already draws.

Offsets are simple because of a choice already made in ``mux/concat_segments.py``: audio is a
plain, unshrunk ``concat`` (D93, T18A), so segment *i*'s narration starts at exactly
``sum(durations_ms[:i])`` in the final video's timeline -- no crossfade-overlap arithmetic to
account for, unlike the video track.

T18B: cue grouping now lives in ``mux/caption_cues.py``, shared with ``_captions.html``'s
in-frame band, so the two can never disagree about where one cue ends and the next begins.
"""

from pathlib import Path

from core.models import Segment
from mux.caption_cues import group_into_cues


def write_srt(segments: list[Segment], dest: Path) -> Path:
    """Write an SRT file covering every segment's narration, in index order. Returns ``dest``.

    Falls back to one cue per segment (the full ``narration`` text, spanning the segment's whole
    ``duration_ms``) when a segment has no ``word_marks`` -- the same degrade-to-something-usable
    rule every other word-timed consumer in this project follows.
    """
    cues: list[tuple[int, int, str]] = []
    offset_ms = 0
    for segment in segments:
        duration_ms = segment.duration_ms or 0
        if segment.word_marks:
            cues.extend(_word_cues(segment, offset_ms))
        elif segment.narration:
            cues.append((offset_ms, offset_ms + duration_ms, segment.narration))
        offset_ms += duration_ms

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(_render_srt(cues), encoding="utf-8")
    return dest


def _word_cues(segment: Segment, segment_offset_ms: int) -> list[tuple[int, int, str]]:
    """One segment's word marks, grouped via ``mux.caption_cues.group_into_cues`` and translated
    into the final video's timeline via ``segment_offset_ms``."""
    return [
        (segment_offset_ms + cue.start_ms, segment_offset_ms + cue.end_ms, cue.text)
        for cue in group_into_cues(segment.word_marks)
    ]


def _render_srt(cues: list[tuple[int, int, str]]) -> str:
    blocks = []
    for index, (start_ms, end_ms, text) in enumerate(cues, start=1):
        blocks.append(f"{index}\n{_timestamp(start_ms)} --> {_timestamp(end_ms)}\n{text}\n")
    return "\n".join(blocks)


def _timestamp(ms: int) -> str:
    """SRT's own format: ``HH:MM:SS,mmm``."""
    ms = max(0, ms)
    hours, rem = divmod(ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    seconds, millis = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"
