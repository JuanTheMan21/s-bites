"""``rendering/geometry_findings.py`` -- parsing the ``"[severity] code: message"`` finding
contract and deciding which fatal findings are worth one bounded re-author attempt (T18I)."""

from rendering.geometry_findings import feedback_note, finding_codes, is_content_retryable


def test_finding_codes_extracts_the_bare_code_token() -> None:
    findings = [
        "[error] canvas_overflow: content exceeds the caption band",
        "[error] escaped_container: element landed outside #root",
    ]
    assert finding_codes(findings) == ["canvas_overflow", "escaped_container"]


def test_finding_codes_falls_back_to_the_raw_text_for_an_unparseable_finding() -> None:
    assert finding_codes(["not in the expected shape"]) == ["not in the expected shape"]


def test_content_sizing_codes_are_retryable() -> None:
    findings = [
        "[error] canvas_overflow: too much content",
        "[error] escaped_container: off-frame",
        "[error] content_overlap: two text blocks overlap",
    ]
    assert is_content_retryable(findings) is True


def test_a_page_error_is_never_retryable_even_alongside_content_findings() -> None:
    # D124's own ReferenceError: compact is not defined -- a bug in OUR templates, not the LLM's
    # content. One non-content code among several content ones must still say no.
    findings = [
        "[error] canvas_overflow: too much content",
        "[error] page_error: ReferenceError: compact is not defined",
    ]
    assert is_content_retryable(findings) is False


def test_sweep_static_is_never_retryable() -> None:
    assert is_content_retryable(["[error] sweep_static: frozen for the whole duration"]) is False


def test_an_unknown_code_defaults_to_not_retryable() -> None:
    # The safe direction to be wrong in -- a code this module has never seen is treated as a
    # possible template bug, not assumed to be content-shaped.
    assert is_content_retryable(["[error] some_new_code: never seen before"]) is False


def test_empty_findings_are_not_retryable() -> None:
    assert is_content_retryable([]) is False


def test_feedback_note_names_every_finding() -> None:
    findings = ["[error] canvas_overflow: too tall", "[error] escaped_container: off-frame"]
    note = feedback_note(findings)
    assert "canvas_overflow" in note
    assert "escaped_container" in note
    for finding in findings:
        assert finding in note
