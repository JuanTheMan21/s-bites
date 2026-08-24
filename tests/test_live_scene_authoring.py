"""The ``scene-authoring`` pack's first contact with a real model -- the same proof T15's
``tests/test_live_plan_segments.py`` gave the ``outline`` and ``scripting`` packs.

``core/graph/nodes/scene_author.py::fill_slots`` against the real ``AzureOpenAILLMProvider`` and the
real, disk-backed ``DiskSkillRegistry`` reading the actual ``runtime_skills/scene-authoring/1.0.md``
and ``house-style/1.0.md`` files. Two completions, a fraction of a cent.

Two intents rather than one, chosen for what they risk: ``code_walkthrough`` is where a model is
most likely to reach for markup (a fenced block, a tag, an inline style), and ``bullet_list`` is the
workhorse every other intent's phrasing rules generalise from.
"""

import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from adapters.azure.llm_provider import AzureOpenAILLMProvider
from adapters.local.skill_registry import DiskSkillRegistry
from core.graph.nodes.scene_author import fill_slots
from core.models import Importance, Segment, VisualIntent
from core.slot_schemas import slot_schema_for
from tests.azure_live import require

pytestmark = pytest.mark.live

MEASURED_MS = 24_000

# "You do not write markup. No HTML, no CSS, no class names" (the pack), plus the fenced-code habit
# a model reaches for unprompted. These are exactly the artifacts that survive into a rendered
# frame: a template either escapes them -- the viewer sees a literal tag -- or trusts them.
#
# A *tag*, not a bare angle bracket. `code_walkthrough`'s lines are real code, where `>` is a
# comparison operator and `->` is a return annotation; banning the character outright would fail
# this test on correct output.
HTML_TAG = re.compile(r"</?[a-zA-Z][a-zA-Z0-9]*(\s[^<>]*)?/?>")
FORBIDDEN_SUBSTRINGS = ("```", "class=", "style=")

NARRATION = (
    "The problem is that the query is built by gluing strings together, so the database has no "
    "way to tell the developer's SQL from the attacker's. A parameterised query sends the "
    "structure first and the values second, and a value can never become a keyword."
)


def _provider() -> AzureOpenAILLMProvider:
    return AzureOpenAILLMProvider(
        endpoint=require("AZURE_OPENAI_ENDPOINT"),
        api_key=require("AZURE_OPENAI_API_KEY"),
        deployment=require("AZURE_OPENAI_DEPLOYMENT"),
        api_version=require("AZURE_OPENAI_API_VERSION"),
    )


def _skills() -> DiskSkillRegistry:
    return DiskSkillRegistry(Path(__file__).resolve().parent.parent / "runtime_skills")


def _a_segment(intent: VisualIntent) -> Segment:
    return Segment(
        index=0,
        title="Why concatenation is the bug",
        summary="Data becomes code when the query is assembled as a string.",
        visual_intent=intent,
        importance=Importance.CRITICAL,
        narration=NARRATION,
        duration_ms=MEASURED_MS,
    )


def _strings(value: Any) -> Iterator[str]:
    """Every string anywhere in a slot payload -- nested lists and objects included, since
    ``diagram_flow``'s nodes and ``code_walkthrough``'s lines are where markup would hide."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


@pytest.mark.parametrize("intent", [VisualIntent.CODE_WALKTHROUGH, VisualIntent.BULLET_LIST])
async def test_the_real_pack_fills_a_scene_without_writing_markup(intent: VisualIntent) -> None:
    llm = _provider()
    try:
        slots = await fill_slots(llm, _skills(), _a_segment(intent), duration_ms=MEASURED_MS)
    finally:
        await llm.aclose()

    # The payload came back as a validated instance of the intent's schema; this is the round trip
    # back through the untyped dict Segment.slots stores it as (D29).
    assert slot_schema_for(intent).model_validate(slots)

    values = list(_strings(slots))
    assert values, "a payload with no text in it would validate and render as an empty frame"
    advice = (
        f"-- the scene-authoring pack's 'you do not write markup' rule isn't landing for "
        f"{intent.value}; consider a runtime_skills/scene-authoring/1.1.md"
    )
    for value in values:
        assert not HTML_TAG.search(value), f"slot text contains a tag: {value!r} {advice}"
        for artifact in FORBIDDEN_SUBSTRINGS:
            assert artifact not in value, f"slot text contains {artifact!r} {advice}"
