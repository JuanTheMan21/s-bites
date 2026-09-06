"""``rendering/still_plan.py`` -- pure, no I/O for the planning half; a tmp_path round-trip for
the JSON sidecar half."""

from pathlib import Path

import pytest

from rendering.still_plan import (
    MAX_STILLS,
    StillSample,
    plan_still_samples,
    read_still_plan,
    settle_seconds,
    write_still_plan,
)


def test_every_cue_start_survives_clamped_into_the_settled_window() -> None:
    """The K1 fix's actual guarantee: caption correctness is never sacrificed for budget."""
    duration_s = 27.66
    cue_starts = [i * 3.0 for i in range(9)]  # the real evidence job's 9-cue segment

    samples = plan_still_samples(cue_starts, [], duration_s=duration_s)

    cue_samples = [s for s in samples if s.is_cue_boundary]
    assert len(cue_samples) == 9
    settle = settle_seconds(duration_s)
    for original, resolved in zip(cue_starts, sorted(s.at_s for s in cue_samples), strict=True):
        assert resolved == pytest.approx(max(original, settle))


def test_result_always_ends_at_the_settled_duration() -> None:
    samples = plan_still_samples([1.0, 2.0], [0.5], duration_s=10.0)

    assert samples[-1].at_s == pytest.approx(10.0)


def test_candidates_are_dropped_when_too_close_to_an_existing_sample() -> None:
    samples = plan_still_samples([5.0], [5.05], duration_s=20.0)

    assert len(samples) == 2  # the cue at 5.0, and the forced end sample -- not a third near 5.0
    assert samples[0].is_cue_boundary


def test_no_cues_no_candidates_still_yields_at_least_the_settle_and_end_states() -> None:
    samples = plan_still_samples([], [], duration_s=21.0)

    assert len(samples) >= 1
    assert samples[-1].at_s == pytest.approx(21.0)
    assert all(not s.is_cue_boundary for s in samples)


def test_cue_boundaries_are_never_dropped_even_when_they_alone_exceed_max_stills() -> None:
    duration_s = 40.0
    cue_starts = [i * 1.0 for i in range(30)]  # more cues than MAX_STILLS

    samples = plan_still_samples(cue_starts, [], duration_s=duration_s)

    assert sum(1 for s in samples if s.is_cue_boundary) >= 29  # settle-window clamp may merge 2


def test_candidates_are_thinned_under_budget_pressure_while_cues_survive() -> None:
    duration_s = 60.0
    cue_starts = [i * 2.0 for i in range(10)]
    candidates = [i * 0.33 for i in range(150)]  # far more candidates than the budget allows

    samples = plan_still_samples(cue_starts, candidates, duration_s=duration_s)

    assert len(samples) <= MAX_STILLS
    assert sum(1 for s in samples if s.is_cue_boundary) == 10


def test_settle_seconds_caps_at_1_5s_but_scales_down_for_short_segments() -> None:
    assert settle_seconds(20.0) == pytest.approx(1.5)
    assert settle_seconds(5.0) == pytest.approx(0.6)


def test_still_plan_round_trips_through_json(tmp_path: Path) -> None:
    samples = [StillSample(0.5, True), StillSample(3.2, False)]

    write_still_plan(tmp_path, samples)
    result = read_still_plan(tmp_path)

    assert result == samples


def test_read_still_plan_returns_none_when_no_sidecar_exists(tmp_path: Path) -> None:
    assert read_still_plan(tmp_path) is None
