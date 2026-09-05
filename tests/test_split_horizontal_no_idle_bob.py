"""T18J: ``_layout_split_horizontal.html``'s counter-phase idle bob (both panels drifting ±6px,
yoyo, for the whole segment) was removed at the user's own direct observation -- "them two cards
floating up and down, that's so unnecessary" -- once it was confirmed to be purely decorative
rather than load-bearing: each panel's own block content already carries real, narration-anchored
motion (its headline, its items), and a fresh composition rendered without the bob still passes
``hyperframes check``'s frozen-sweep guard (``motion.findings`` empty, verified against a real
segment's actual scene data). The shared background pulse (`_tokens.html::background_script`) and
the title underline glow stay -- both are documented anti-freeze fallbacks for when nothing else
in a scene is moving (a title card with no key_terms; any layout's own base layer), not decoration
layered on top of already-live content the way the panel bob was.
"""

import re
from pathlib import Path

from core.block_types import BlockType
from core.scene_schemas import ComposedBlock, ComposedScene
from rendering.compose import compose_scene
from tests.block_examples import EXAMPLES
from tests.segment_examples import a_segment

DURATION_MS = 21_000


def test_split_horizontal_has_no_perpetual_panel_bob(tmp_path: Path) -> None:
    scene = ComposedScene(
        motif="terminal",
        layout="split_horizontal",
        blocks=[
            ComposedBlock(
                block_type=BlockType.TEXT_PANEL,
                role="left",
                anchor_phrase=None,
                payload=EXAMPLES[BlockType.TEXT_PANEL],
            ),
            ComposedBlock(
                block_type=BlockType.TEXT_PANEL,
                role="right",
                anchor_phrase=None,
                payload=EXAMPLES[BlockType.TEXT_PANEL],
            ),
        ],
        continues_previous=False,
    )
    segment = a_segment(0, duration_ms=DURATION_MS).model_copy(update={"scene": scene.model_dump()})

    dest = compose_scene(segment, tmp_path)
    html = dest.read_text(encoding="utf-8")

    # The background pulse (_tokens.html) legitimately shares this same "yoyo, duration-aware
    # repeat" shape and the `reps` variable name -- so the specific, unique thing removed is a
    # perpetual tween targeting a PANEL's own "-region" element, not the pattern in general.
    assert not re.search(r'"#b[01]-region"[^;]*yoyo: true', html), (
        "no panel region should carry its own perpetual yoyo tween"
    )
    # The regions themselves are untouched -- only their own perpetual y-bob is removed.
    assert re.search(r'id="b0-region"', html)
    assert re.search(r'id="b1-region"', html)
