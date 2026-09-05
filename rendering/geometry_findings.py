"""Parsing the ``"[severity] code: message"`` string contract both ``RenderBackend.lint`` and
``RenderBackend.validate_geometry`` return (``adapters/local/render_backend.py``), to decide
whether a fatal finding is worth one bounded re-author attempt (T18I, ``core/graph/nodes/
scene_reauthor.py``) or should go straight to the safe fallback (``core/graph/nodes/
scene_fallback.py``).

**The retryable/non-retryable split is the whole point of this module, and it is deliberately
narrow.** A finding whose CODE names a content-sizing problem (``canvas_overflow``,
``escaped_container``, ``content_overlap`` -- every one T18H's own real renders actually produced,
D124) means the LLM's authored content was too big or too dense for the frame, which a fresh
authoring attempt with feedback can plausibly fix. A finding whose code names our OWN template
breaking (``page_error``, ``sweep_static`` -- D124's own ``ReferenceError: compact is not
defined``, caught by this same gate) is a bug in code, not content, and retrying it burns an LLM
call while hiding a regression that should have failed loudly. When a composition returns findings
of both kinds together, the non-retryable one wins -- re-authoring cannot fix a template bug, so
there is nothing a retry buys.
"""

import re

# T18H/D124's own real-render vocabulary -- extend this only with a code actually observed in a
# real render's own findings, never on a guess (this module's own docstring: a code absent here
# defaults to NOT retryable, which is the safe direction to be wrong in).
#
# T18I (this session's own closing render, not a guess either): two segments failed with
# ['content_overlap', 'text_occluded'] and skipped the retry entirely -- `text_occluded` was
# absent here, so `is_content_retryable` returned False on a finding that is exactly as
# content-shaped as the other three (something's text is hidden behind other content because
# there was too much of it) and went straight to the fallback title card instead of getting the
# one bounded re-author attempt that might have fixed it. `array_grid`'s own INTENTIONAL
# occlusion (a strikethrough over an eliminated value) already opts out via
# `data-layout-allow-occlusion` before this code ever fires, so an unintentional one reaching
# `validate_geometry` at all is a real content-sizing problem, not a false positive.
_CONTENT_SIZING_CODES = frozenset(
    {
        "canvas_overflow",
        "escaped_container",
        "content_overlap",
        "text_occluded",
    }
)

_FINDING_RE = re.compile(r"^\[(?P<severity>\w+)\]\s*(?P<code>[\w.-]+):\s*(?P<message>.*)$")


def finding_codes(findings: list[str]) -> list[str]:
    """The bare ``code`` token from each finding string, in order. A finding that doesn't match
    the expected shape contributes its own raw text instead of being silently dropped -- an
    unparseable finding is itself worth seeing, not hiding."""
    codes = []
    for finding in findings:
        match = _FINDING_RE.match(finding)
        codes.append(match.group("code") if match else finding)
    return codes


def is_content_retryable(findings: list[str]) -> bool:
    """True only when EVERY finding's code is content-sizing (see module docstring) -- one
    template-bug finding among several content ones is enough to say no, since re-authoring
    content cannot fix a code bug, and there would be nothing left to gain from the attempt."""
    codes = finding_codes(findings)
    return bool(codes) and all(code in _CONTENT_SIZING_CODES for code in codes)


def feedback_note(findings: list[str]) -> str:
    """The corrective appendix text handed to ``scene_reauthor.reauthor_scene`` -- names exactly
    what overflowed/escaped/overlapped, in the same "## Revise" shape ``visual_plan.py
    ::_reask_appendix`` already uses for its own single corrective re-ask."""
    lines = [
        "## Revise",
        "The previous version of this scene's content failed a real rendering check -- it was "
        "too large, too dense, or escaped its frame. Keep the same block choices, but make the "
        "content itself shorter, sparser, or smaller so it fits within the frame. The specific "
        "problems found:",
    ]
    lines.extend(f"- {finding}" for finding in findings)
    return "\n".join(lines)
