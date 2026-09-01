"""A believable content payload for every block type.

Renamed from ``tests/slot_examples.py`` (T18B): payloads are keyed by ``BlockType`` now, one
fragment of a scene, not a whole one chosen per intent. Not a test module. These are shared
fixtures: ``tests/test_block_schemas.py`` validates each one against its schema today, and
``rendering/templates/_block_*.html`` renders against the same payloads, so a block partial and
the schema it consumes are exercised with identical input.

Realistic rather than minimal, on purpose. A payload of ``{"headline": "x"}`` proves the schema
parses; one with three real items shows whether the block still reads at 1080p.

T18G: the T18C-onward block types moved to ``tests/block_examples_extra.py`` once this file
crossed the 200-line ceiling -- ``EXAMPLES`` merges both, so nothing importing ``EXAMPLES`` needs
to know or care where a given block type's fixture actually lives.
"""

from typing import Any

from core.block_types import BlockType
from tests.block_examples_extra import EXTRA_EXAMPLES

# One believable payload per block type, T18A/T18B's original six. These double as the fixtures
# the block partials render against, so they are realistic rather than minimal.
_CORE_EXAMPLES: dict[BlockType, dict[str, Any]] = {
    BlockType.TITLE: {
        "headline": "SQL Injection",
        "subtitle": "How one quote breaks a query",
        "key_terms": [
            {"text": "Untrusted input", "anchor_phrase": "untrusted input"},
            {"text": "Query injection", "anchor_phrase": "breaks the query"},
        ],
    },
    BlockType.TEXT_PANEL: {
        "headline": "Why it works",
        "items": [
            {
                "text": "Untrusted input reaches the query text.",
                "anchor_phrase": "untrusted input reaches the query",
            },
            {
                "text": "The parser cannot tell data from code.",
                "anchor_phrase": "the parser cannot tell data from code",
            },
            {
                "text": "The database executes whatever it parsed.",
                "anchor_phrase": "the database executes whatever it parsed",
            },
        ],
    },
    BlockType.STAT_CALLOUT: {
        "value": "1 in 5",
        "unit": None,
        "context": "of breaches begin with an injection flaw.",
        # "1 in 5" is a ratio phrasing, not a clean number a count-up should animate -- the
        # schema's own guidance for when value_number stays null. See
        # tests/test_block_schemas.py::EXAMPLE_WITH_COUNT_UP for the populated case.
        "value_number": None,
        "prefix": None,
        "suffix": None,
    },
    BlockType.CODE_PANEL: {
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
}

EXAMPLES: dict[BlockType, dict[str, Any]] = {**_CORE_EXAMPLES, **EXTRA_EXAMPLES}

# A second stat_callout payload, exercising the T18A count-up path EXAMPLES's own entry
# deliberately leaves null. Not part of EXAMPLES because that dict is one fixture per block type,
# shared by every template/schema test that iterates BlockType -- this is additive coverage for
# the one block type with two meaningfully different rendering paths.
STAT_CALLOUT_WITH_COUNT_UP: dict = {
    "value": "200,000",
    "unit": None,
    "context": "tokens spent across the intro sequence alone.",
    "value_number": 200_000,
    "prefix": None,
    "suffix": None,
}
