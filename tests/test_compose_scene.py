"""``rendering/compose.py`` -- offline, no browser, no CLI. Confirms the Jinja rendering and the
directory-layout decision T17's plan settles: every composition lands as the sole
``dest_dir/index.html``, which is what ``hyperframes lint`` (D60) hard-requires.

T18B: parametrized by ``BlockType`` (each rendered alone, ``SINGLE`` layout) rather than
``VisualIntent`` -- ``compose_scene`` now dispatches on ``SceneLayout``, not the intent, and a
segment's scene carries a list of blocks rather than one intent's slot payload.
"""

import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from core.block_types import BlockType
from core.scene_schemas import ComposedBlock, ComposedScene
from interfaces.tts_provider import WordMark
from rendering.compose import compose_scene
from tests.block_examples import EXAMPLES
from tests.segment_examples import a_segment

DURATION_MS = 21_000


def _a_composed_segment(block_type: BlockType, *, payload=None):
    scene = ComposedScene(
        motif="terminal",
        layout="single",
        blocks=[
            ComposedBlock(
                block_type=block_type,
                role="role",
                anchor_phrase=None,
                payload=EXAMPLES[block_type] if payload is None else payload,
            )
        ],
        continues_previous=False,
    )
    return a_segment(0, duration_ms=DURATION_MS).model_copy(update={"scene": scene.model_dump()})


@pytest.mark.parametrize("block_type", list(BlockType))
def test_it_writes_index_html_and_the_vendored_gsap_it_references(
    tmp_path: Path, block_type: BlockType
) -> None:
    """T18A: the composition directory is no longer literally one file -- ``compose_scene`` also
    copies the vendored ``gsap.min.js`` every layout now loads via a relative ``./gsap.min.js``
    (no more jsDelivr CDN, so a render needs no network egress). Verified directly against
    ``hyperframes check`` that a sibling file does not violate D60's actual constraint, which is
    the entry file's name (``index.html``) and location, not the directory being literally empty
    otherwise.
    """
    segment = _a_composed_segment(block_type)
    dest_dir = tmp_path / "segments" / "0" / "composition"

    dest = compose_scene(segment, dest_dir)

    assert dest == dest_dir / "index.html"
    assert set(dest_dir.iterdir()) == {dest, dest_dir / "gsap.min.js"}
    assert (dest_dir / "gsap.min.js").stat().st_size > 0
    assert "cdn.jsdelivr" not in dest.read_text(encoding="utf-8")


@pytest.mark.parametrize("block_type", list(BlockType))
def test_the_root_carries_the_measured_duration_in_seconds_not_milliseconds(
    tmp_path: Path, block_type: BlockType
) -> None:
    segment = _a_composed_segment(block_type)

    dest = compose_scene(segment, tmp_path)

    html = dest.read_text(encoding="utf-8")
    assert 'data-composition-id="' in html
    assert 'data-duration="21.0"' in html
    assert "21000" not in html


def test_an_unmeasured_segment_raises_before_any_template_is_touched(tmp_path: Path) -> None:
    segment = _a_composed_segment(BlockType.TITLE).model_copy(update={"duration_ms": None})

    with pytest.raises(ValueError, match="no measured duration_ms"):
        compose_scene(segment, tmp_path)

    assert list(tmp_path.iterdir()) == []


def test_a_segment_with_no_scene_raises_before_any_template_is_touched(tmp_path: Path) -> None:
    segment = a_segment(0, duration_ms=DURATION_MS)

    with pytest.raises(ValueError, match="no scene"):
        compose_scene(segment, tmp_path)

    assert list(tmp_path.iterdir()) == []


def test_a_malformed_block_payload_raises_validation_error_not_a_template_error(
    tmp_path: Path,
) -> None:
    """D29: validated back through ``block_schema_for`` at the point of use, so a bad payload
    fails with a clear schema error rather than a confusing Jinja ``UndefinedError`` mid-render.
    """
    segment = _a_composed_segment(
        BlockType.STAT_CALLOUT,
        payload={"unit": "%"},  # missing required `value`/`context`
    )

    with pytest.raises(ValidationError):
        compose_scene(segment, tmp_path)


@pytest.mark.parametrize("block_type", list(BlockType))
def test_a_split_horizontal_scene_has_no_id_collision(
    tmp_path: Path, block_type: BlockType
) -> None:
    """The layout no test previously exercised end to end (found by review): SPLIT_HORIZONTAL
    puts a block's own markup inside a layout-owned wrapper carrying that block's ``prefix`` --
    a real risk that a block's *own* internal id (e.g. code_panel's own "{prefix}-panel" wrapper)
    collides with the layout's, found this way for exactly that pair (code_panel, also found by
    a real ``hyperframes check`` run flagging the resulting duplicate-id as an
    ``overlapping_gsap_tweens`` warning, not just by reading the templates)."""
    scene = ComposedScene(
        motif="terminal",
        layout="split_horizontal",
        blocks=[
            ComposedBlock(
                block_type=block_type, role="left", anchor_phrase=None, payload=EXAMPLES[block_type]
            ),
            ComposedBlock(
                block_type=block_type,
                role="right",
                anchor_phrase=None,
                payload=EXAMPLES[block_type],
            ),
        ],
        continues_previous=False,
    )
    segment = a_segment(0, duration_ms=DURATION_MS).model_copy(update={"scene": scene.model_dump()})

    dest = compose_scene(segment, tmp_path)
    html = dest.read_text(encoding="utf-8")

    ids = re.findall(r'id="([^"]+)"', html)
    assert len(ids) == len(set(ids)), f"duplicate element ids across the two panels: {ids}"


def test_captions_render_every_words_text_with_unique_ids_across_cues(tmp_path: Path) -> None:
    """Found by review: a caption span with no text content and colliding ids across cues both
    passed the old (word_marks-less) test fixtures silently. Nine words forces two cues
    (``MAX_WORDS_PER_CUE`` is 8), which is what actually exercises the cross-cue id path."""
    words = [WordMark(text=f"word{i}", offset_ms=i * 300, duration_ms=250) for i in range(9)]
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
    segment = a_segment(0, duration_ms=DURATION_MS).model_copy(
        update={"scene": scene.model_dump(), "word_marks": words}
    )

    dest = compose_scene(segment, tmp_path)
    html = dest.read_text(encoding="utf-8")

    for word in words:
        assert f">{word.text}<" in html, f"{word.text!r} never appears as visible caption text"
    span_ids = re.findall(r'class="ls-cap-word"[^>]*id="([^"]+)"|id="(ls-cap-[^"]+)"', html)
    flat_ids = [a or b for a, b in span_ids]
    assert len(flat_ids) == len(set(flat_ids)), f"duplicate caption word ids: {flat_ids}"
