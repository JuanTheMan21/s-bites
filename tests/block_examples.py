"""A believable content payload for every block type.

Renamed from ``tests/slot_examples.py`` (T18B): payloads are keyed by ``BlockType`` now, one
fragment of a scene, not a whole one chosen per intent. Not a test module. These are shared
fixtures: ``tests/test_block_schemas.py`` validates each one against its schema today, and
``rendering/templates/_block_*.html`` renders against the same payloads, so a block partial and
the schema it consumes are exercised with identical input.

Realistic rather than minimal, on purpose. A payload of ``{"headline": "x"}`` proves the schema
parses; one with three real items shows whether the block still reads at 1080p.
"""

from typing import Any

from core.block_types import BlockType

# One believable payload per block type. These double as the fixtures the block partials render
# against, so they are realistic rather than minimal.
EXAMPLES: dict[BlockType, dict[str, Any]] = {
    BlockType.TITLE: {
        "headline": "SQL Injection",
        "subtitle": "How one quote breaks a query",
    },
    BlockType.TEXT_PANEL: {
        "headline": "Why it works",
        "items": [
            "Untrusted input reaches the query text.",
            "The parser cannot tell data from code.",
            "The database executes whatever it parsed.",
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
    BlockType.ARRAY_GRID: {
        "headline": "Searching a sorted list",
        "orientation": "horizontal",
        "cells": ["2", "5", "8", "12", "16", "23", "38", "56", "72", "91"],
        "steps": [
            {
                "op": "narrow",
                "anchor_phrase": "check the middle",
                "remaining_start": 0,
                "remaining_end": 5,
                "end_operation": "none",
            },
            {
                "op": "narrow",
                "anchor_phrase": "narrow again",
                "remaining_start": 3,
                "remaining_end": 5,
                "end_operation": "none",
            },
        ],
    },
    BlockType.GRAPH_DIAGRAM: {
        "headline": "The attack path",
        "layout": "chain",
        "nodes": [
            {"id": "n1", "label": "Form input", "caption": "An apostrophe and a comment marker"},
            {"id": "n2", "label": "String concatenation", "caption": None},
            {
                "id": "n3",
                "label": "Database executes",
                "caption": "Now running the attacker's clause",
            },
        ],
        "edges": [
            {"from_id": "n1", "to_id": "n2"},
            {"from_id": "n2", "to_id": "n3"},
        ],
        "positions": [],
        "traversal": [],
    },
    BlockType.CODE_DIFF: {
        "headline": "Parameterizing the query",
        "language": "python",
        "lines": [
            {"op": "context", "text": "name = request.args['name']"},
            {
                "op": "remove",
                "text": 'query = "SELECT * FROM users WHERE name = \'" + name + "\'"',
            },
            {"op": "add", "text": 'query = "SELECT * FROM users WHERE name = %s"'},
            {"op": "add", "text": "cursor.execute(query, (name,))"},
        ],
        "caption": "The driver escapes the value instead of the app splicing it in.",
    },
    BlockType.SEQUENCE_DIAGRAM: {
        "headline": "A parameterized query round trip",
        "actors": [
            {"id": "app", "label": "App"},
            {"id": "db", "label": "Database"},
        ],
        "messages": [
            {
                "anchor_phrase": "sends the query and the value separately",
                "from_id": "app",
                "to_id": "db",
                "label": "query + params",
            },
            {
                "anchor_phrase": "the database returns the matching rows",
                "from_id": "db",
                "to_id": "app",
                "label": "rows",
            },
        ],
    },
    BlockType.TIMELINE: {
        "headline": "How the fix landed",
        "events": [
            {
                "anchor_phrase": "the bug was first reported",
                "label": "Reported",
                "date_label": "Day 1",
            },
            {"anchor_phrase": "a patch went out", "label": "Patched", "date_label": "Day 3"},
        ],
    },
}

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
