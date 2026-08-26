"""A believable slot payload for every visual intent.

Not a test module. These are shared fixtures: ``tests/test_slot_schemas.py`` validates each one
against its schema today, and T17 renders its Jinja templates against the same payloads, so a
template and the schema it consumes are exercised with identical input.

Realistic rather than minimal, on purpose. A payload of ``{"headline": "x"}`` proves the schema
parses; one with three real bullets shows whether the template still reads at 1080p.
"""

from typing import Any

from core import VisualIntent

# One believable payload per intent. These double as the fixtures T17's templates render
# against, so they are realistic rather than minimal.
EXAMPLES: dict[VisualIntent, dict[str, Any]] = {
    VisualIntent.TITLE_CARD: {
        "headline": "SQL Injection",
        "subtitle": "How one quote breaks a query",
    },
    VisualIntent.BULLET_LIST: {
        "headline": "Why it works",
        "bullets": [
            "Untrusted input reaches the query text.",
            "The parser cannot tell data from code.",
            "The database executes whatever it parsed.",
        ],
    },
    VisualIntent.COMPARISON: {
        "headline": "Concatenation versus binding",
        "left_label": "Unsafe",
        "left_items": ["Input becomes query text.", "Quoting is the only defence."],
        "right_label": "Safe",
        "right_items": ["Input stays a value.", "The plan is fixed before input arrives."],
    },
    VisualIntent.DIAGRAM_FLOW: {
        "headline": "The attack path",
        "nodes": [
            {"label": "Form input", "caption": "An apostrophe and a comment marker"},
            {"label": "String concatenation", "caption": None},
            {"label": "Database executes", "caption": "Now running the attacker's clause"},
        ],
    },
    VisualIntent.CODE_WALKTHROUGH: {
        "headline": "The vulnerable line",
        "language": "python",
        "lines": [
            "name = request.args['name']",
            'query = "SELECT * FROM users WHERE name = \'" + name + "\'"',
            "cursor.execute(query)",
        ],
        "highlight_lines": [2],
        "caption": "The value is spliced into the query before the parser ever runs.",
    },
    VisualIntent.STAT_CALLOUT: {
        "value": "1 in 5",
        "unit": None,
        "context": "of breaches begin with an injection flaw.",
        # "1 in 5" is a ratio phrasing, not a clean number a count-up should animate -- the
        # schema's own guidance for when value_number stays null. See
        # tests/test_slot_schemas.py::EXAMPLE_WITH_COUNT_UP for the populated case.
        "value_number": None,
        "prefix": None,
        "suffix": None,
    },
}

# A second stat_callout payload, exercising the T18A count-up path EXAMPLES's own entry
# deliberately leaves null. Not part of EXAMPLES because that dict is one fixture per intent,
# shared by every template/schema test that iterates VisualIntent -- this is additive coverage
# for the one intent with two meaningfully different rendering paths.
STAT_CALLOUT_WITH_COUNT_UP: dict = {
    "value": "200,000",
    "unit": None,
    "context": "tokens spent across the intro sequence alone.",
    "value_number": 200_000,
    "prefix": None,
    "suffix": None,
}
