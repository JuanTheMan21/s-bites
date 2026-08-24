"""``rendering/compose.py`` -- offline, no browser, no CLI. Confirms the Jinja rendering and the
directory-layout decision the T17 plan settles: every composition lands as the sole
``dest_dir/index.html``, which is what ``hyperframes lint`` (D60) hard-requires.
"""

from pathlib import Path

import pytest
from pydantic import ValidationError

from core import VisualIntent
from rendering.compose import compose_scene
from tests.segment_examples import a_segment
from tests.slot_examples import EXAMPLES

DURATION_MS = 21_000


@pytest.mark.parametrize("intent", list(VisualIntent))
def test_it_writes_the_sole_index_html_in_the_given_directory(
    tmp_path: Path, intent: VisualIntent
) -> None:
    segment = a_segment(0, intent=intent, duration_ms=DURATION_MS).model_copy(
        update={"slots": EXAMPLES[intent]}
    )
    dest_dir = tmp_path / "segments" / "0" / "composition"

    dest = compose_scene(segment, dest_dir)

    assert dest == dest_dir / "index.html"
    assert list(dest_dir.iterdir()) == [dest]


@pytest.mark.parametrize("intent", list(VisualIntent))
def test_the_root_carries_the_measured_duration_in_seconds_not_milliseconds(
    tmp_path: Path, intent: VisualIntent
) -> None:
    segment = a_segment(0, intent=intent, duration_ms=DURATION_MS).model_copy(
        update={"slots": EXAMPLES[intent]}
    )

    dest = compose_scene(segment, tmp_path)

    html = dest.read_text(encoding="utf-8")
    assert 'data-composition-id="' in html
    assert 'data-duration="21.0"' in html
    assert "21000" not in html


def test_an_unmeasured_segment_raises_before_any_template_is_touched(tmp_path: Path) -> None:
    segment = a_segment(0, intent=VisualIntent.TITLE_CARD, duration_ms=None).model_copy(
        update={"slots": EXAMPLES[VisualIntent.TITLE_CARD]}
    )

    with pytest.raises(ValueError, match="no measured duration_ms"):
        compose_scene(segment, tmp_path)

    assert list(tmp_path.iterdir()) == []


def test_a_malformed_slots_payload_raises_validation_error_not_a_template_error(
    tmp_path: Path,
) -> None:
    """D29: validated back through ``slot_schema_for`` at the point of use, so a bad payload fails
    with a clear schema error rather than a confusing ``jinja2.UndefinedError`` mid-render."""
    segment = a_segment(0, intent=VisualIntent.STAT_CALLOUT, duration_ms=DURATION_MS).model_copy(
        update={"slots": {"unit": "%"}}  # missing the required `value` and `context` fields
    )

    with pytest.raises(ValidationError):
        compose_scene(segment, tmp_path)
