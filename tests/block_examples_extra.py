"""Believable content payloads for the T18C-onward block types -- split out of
``tests/block_examples.py`` (T18G) once that file crossed the 200-line ceiling. Not a test
module; see that file's own docstring for the shared-fixture rationale. ``EXAMPLES`` there merges
this dict in, so nothing importing ``EXAMPLES`` needs to know this split exists.
"""

from typing import Any

from core.block_types import BlockType

EXTRA_EXAMPLES: dict[BlockType, dict[str, Any]] = {
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
            {
                "id": "n1",
                "label": "Form input",
                "caption": "An apostrophe and a comment marker",
                "anchor_phrase": "an apostrophe and a comment marker",
            },
            {
                "id": "n2",
                "label": "String concatenation",
                "caption": None,
                "anchor_phrase": "concatenated straight into the query",
            },
            {
                "id": "n3",
                "label": "Database executes",
                "caption": "Now running the attacker's clause",
                "anchor_phrase": "the database executes whatever it parsed",
            },
        ],
        "edges": [
            {"from_id": "n1", "to_id": "n2", "label": None},
            {"from_id": "n2", "to_id": "n3", "label": None},
        ],
        "positions": [],
        "traversal": [],
    },
    BlockType.CODE_DIFF: {
        "headline": "Parameterizing the query",
        "language": "python",
        "lines": [
            {
                "op": "context",
                "text": "name = request.args['name']",
                "anchor_phrase": "the value is spliced into the query",
            },
            {
                "op": "remove",
                "text": 'query = "SELECT * FROM users WHERE name = \'" + name + "\'"',
                "anchor_phrase": "before the parser ever runs",
            },
            {
                "op": "add",
                "text": 'query = "SELECT * FROM users WHERE name = %s"',
                "anchor_phrase": "the driver escapes the value",
            },
            {
                "op": "add",
                "text": "cursor.execute(query, (name,))",
                "anchor_phrase": "instead of the app splicing it in",
            },
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
    BlockType.ICON_PANEL: {
        "headline": "What a WAF blocks",
        "items": [
            {
                "icon": "shield",
                "label": "SQL injection",
                "anchor_phrase": "blocks sql injection attempts",
            },
            {
                "icon": "warning",
                "label": "Malformed input",
                "anchor_phrase": "flags malformed input",
            },
            {
                "icon": "lock",
                "label": "Known exploits",
                "anchor_phrase": "known exploit signatures",
            },
        ],
    },
}
