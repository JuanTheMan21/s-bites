"""``rendering/geometry_findings.py::is_fatal_geometry_finding`` -- T18J's fix for the actual root
cause of two user-flagged real-render defects (a graph-diagram caption overlap, a sequence-diagram
overlap): both were genuinely detected by ``hyperframes check`` but reported at ``[warning]``
severity, and ``render_segment.py``'s old blanket "warnings never block" rule (correct for
``lint()``'s own stylistic nags) was silently waving them through. Re-checking both real
compositions at higher sample density (9 -> 21) and with ``--at-transitions`` enabled left the
severity unchanged (occurrences rose, classification did not) -- confirming this is a
classification-filter fix, not a sampling-density one.
"""

from rendering.geometry_findings import is_fatal_geometry_finding


def test_error_severity_is_always_fatal() -> None:
    assert is_fatal_geometry_finding("[error] canvas_overflow: too much content")
    assert is_fatal_geometry_finding("[error] page_error: ReferenceError")


def test_info_severity_is_never_fatal() -> None:
    assert not is_fatal_geometry_finding("[info] canvas_overflow: barely, one sample")


def test_warning_severity_content_sizing_code_is_fatal() -> None:
    """The exact live-confirmed case: content_overlap at [warning] severity, previously waved
    through, is exactly what a user watched and reported as broken."""
    assert is_fatal_geometry_finding("[warning] content_overlap: two text blocks overlap")
    assert is_fatal_geometry_finding("[warning] canvas_overflow: breaches the frame")
    assert is_fatal_geometry_finding("[warning] escaped_container: outside its own container")
    assert is_fatal_geometry_finding("[warning] text_occluded: hidden behind other content")


def test_warning_severity_non_content_code_stays_non_fatal() -> None:
    """A template/code-shaped warning (not in the content-sizing vocabulary) must still be
    exempt -- this is what keeps a stylistic nag like sweep_static from blocking every render."""
    assert not is_fatal_geometry_finding("[warning] sweep_static: nothing moved")


def test_an_unparseable_finding_is_treated_as_fatal() -> None:
    """Matches finding_codes' own philosophy: a finding that doesn't fit the expected shape is
    itself worth failing loudly on, not silently passing through as harmless."""
    assert is_fatal_geometry_finding("not a real finding string at all")
