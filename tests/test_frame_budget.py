"""How large a frame budget is, as opposed to how it gets spent.

Split from ``tests/test_tier_resolver.py`` the same way D35 split the modules: the resolver
spends a budget, this decides how big one is, and nothing here knows what a tier is.
"""

import pytest

from core import scale_frame_budget
from core.models import DEFAULT_TARGET_DURATION_MS


def test_the_frame_budget_scales_with_length_but_stops_at_the_ceiling() -> None:
    """Linear with no cap turns a 20-minute video into a 20-minute render (D16)."""
    assert scale_frame_budget(600, 7 * 60 * 1000) == 600
    assert scale_frame_budget(600, 14 * 60 * 1000) == 1200
    assert scale_frame_budget(600, 30 * 60 * 1000) == 1200
    assert scale_frame_budget(600, 3 * 60 * 1000) < 600


def test_the_default_length_gets_exactly_the_base_budget() -> None:
    """FRAME_BUDGET is calibrated for a default-length video, so that case must not drift."""
    assert scale_frame_budget(600, DEFAULT_TARGET_DURATION_MS) == 600


def test_a_negative_target_duration_floors_at_zero_rather_than_going_negative() -> None:
    """A negative budget would make the resolver raise, several layers from the real mistake."""
    assert scale_frame_budget(600, -1) == 0


def test_a_negative_base_budget_is_refused() -> None:
    with pytest.raises(ValueError, match="base_frames cannot be negative"):
        scale_frame_budget(-1, DEFAULT_TARGET_DURATION_MS)


def test_a_ceiling_below_the_base_budget_is_refused() -> None:
    """max_multiple under 1 would scale a default-length video *down* -- a silent budget cut."""
    with pytest.raises(ValueError, match="max_multiple cannot be below 1"):
        scale_frame_budget(600, DEFAULT_TARGET_DURATION_MS, max_multiple=0.5)
