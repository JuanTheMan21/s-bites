"""``rendering/templates/_captions.html``'s caption band vs. ``hyperframes check
--caption-zone`` -- offline, no browser, no CLI (the check itself needs the real toolchain; this
only confirms the markup carries the exemption it needs).

T18K: a real render found this missing. ``hyperframes check --caption-zone`` flags ANY element
sitting in the reserved caption band unless it carries ``data-layout-allow-caption-zone``, and
``_captions.html``'s own band never carried it. It only ever passed by accident: the last cue
used to hide at its own ``end_ms``, safely before ``validate_geometry``'s end-of-timeline sample
landed while a cue was still visible. Extending the last cue's visible window to
``duration_sec`` (this same task, so trailing silence no longer shows a blank band) made that
sample catch a real caption word sitting in its own band, with nothing marking it as allowed to
be there.
"""

from pathlib import Path

from core.block_types import BlockType
from core.scene_schemas import ComposedBlock, ComposedScene
from interfaces.tts_provider import WordMark
from rendering.compose import compose_scene
from tests.block_examples import EXAMPLES
from tests.segment_examples import a_segment

DURATION_MS = 21_000


def test_the_caption_layer_is_exempt_from_the_caption_zone_geometry_check(tmp_path: Path) -> None:
    scene = ComposedScene(
        motif="terminal",
        layout="single",
        blocks=[
            ComposedBlock(
                block_type=BlockType.TITLE,
                role="role",
                anchor_phrase=None,
                payload=EXAMPLES[BlockType.TITLE],
            )
        ],
        continues_previous=False,
    )
    word_marks = [
        WordMark(text=w, offset_ms=i * 300, duration_ms=250)
        for i, w in enumerate(["A", "name", "becomes", "an", "address"])
    ]
    segment = a_segment(0, duration_ms=DURATION_MS).model_copy(
        update={"scene": scene.model_dump(), "word_marks": word_marks}
    )

    dest = compose_scene(segment, tmp_path)
    html = dest.read_text(encoding="utf-8")

    assert 'id="ls-captions"' in html
    assert "data-layout-allow-caption-zone" in html
