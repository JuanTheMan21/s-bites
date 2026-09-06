"""T18M: ``core/graph/nodes/scene_fallback.py``'s narration-derived ``key_terms`` -- fixing the
hardcoded ``key_terms=[]`` that left the fallback title card's chip-staging animation with
nothing to stage, a static wall of text for 21-31s on a real render's four degraded segments."""

from core.graph.nodes.scene_fallback import title_card_scene
from rendering.anchors import resolve_anchor
from tests.segment_examples import a_segment


def _word_marks(narration: str):
    from interfaces.tts_provider import WordMark

    words = narration.replace(".", "").replace(",", "").split()
    return [WordMark(text=w, offset_ms=i * 300, duration_ms=250) for i, w in enumerate(words)]


def test_fallback_card_gets_narration_derived_chips() -> None:
    narration = (
        "The derivative measures instantaneous rate of change. "
        "It is defined as a limit. "
        "This limit, if it exists, gives the slope."
    )
    segment = a_segment(0).model_copy(update={"narration": narration})

    scene = title_card_scene(segment, motif="terminal")

    payload = scene.blocks[0].payload
    assert payload["key_terms"]
    assert len(payload["key_terms"]) <= 4


def test_every_chip_anchor_is_a_verbatim_narration_fragment_that_resolves() -> None:
    narration = (
        "The derivative measures instantaneous rate of change. "
        "It is defined as a limit. "
        "This limit, if it exists, gives the slope."
    )
    segment = a_segment(0).model_copy(update={"narration": narration})
    word_marks = _word_marks(narration)

    scene = title_card_scene(segment, motif="terminal")

    for term in scene.blocks[0].payload["key_terms"]:
        assert term["anchor_phrase"] in narration
        assert resolve_anchor(word_marks, term["anchor_phrase"]) is not None


def test_no_narration_degrades_to_no_chips() -> None:
    segment = a_segment(0).model_copy(update={"narration": None})

    scene = title_card_scene(segment, motif="terminal")

    assert scene.blocks[0].payload["key_terms"] == []


def test_long_summary_is_truncated_for_the_subtitle() -> None:
    long_summary = "word " * 40
    segment = a_segment(0).model_copy(update={"summary": long_summary.strip()})

    scene = title_card_scene(segment, motif="terminal")

    assert len(scene.blocks[0].payload["subtitle"]) < len(long_summary.strip())
