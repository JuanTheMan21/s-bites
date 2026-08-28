"""``core/graph/nodes/scene_author.py::fill_block`` -- the call that fills one block's content.

Tested directly (not through the graph) because what it *sends* is the only place "the skill
pack demonstrably changes behaviour" can be observed against a fake that ignores prompt content
when answering. The node-level guarantees (``author_scene`` filling every planned block, both
refusals) live in ``tests/test_author_scene_node.py``, split out when the combined file crossed
the 200-line ceiling.
"""

import pytest

from core.block_schemas import block_schema_for
from core.block_types import BlockType
from core.graph.nodes.scene_author import fill_block
from core.models import VisualIntent
from tests.fakes import FakeLLMProvider
from tests.scene_author_fixtures import (
    MEASURED_MS,
    a_payload_for,
    a_planned_block,
    a_skill_registry,
)
from tests.segment_examples import a_segment


async def test_the_scene_authoring_and_house_style_packs_reach_the_call() -> None:
    skills = a_skill_registry(
        scene_authoring="DISTINCTIVE SCENE TEXT", house_style="DISTINCTIVE HOUSE STYLE"
    )
    llm = FakeLLMProvider([a_payload_for(BlockType.TEXT_PANEL)])

    await fill_block(
        llm,
        skills,
        a_segment(0, intent=VisualIntent.BULLET_LIST),
        a_planned_block(BlockType.TEXT_PANEL),
        duration_ms=MEASURED_MS,
    )

    call = llm.calls[0]
    assert "DISTINCTIVE SCENE TEXT" in call.prompt
    assert call.system == "DISTINCTIVE HOUSE STYLE"


@pytest.mark.parametrize("block_type", list(BlockType))
async def test_the_schema_asked_for_is_the_blocks_own(block_type: BlockType) -> None:
    """The whole indirection D2 rests on, now one level down: the model is never asked for
    markup, it is asked for exactly the payload this block's type consumes. Every block type,
    not a sample -- a mapping tested on one member is tested nowhere (D39)."""
    llm = FakeLLMProvider([a_payload_for(block_type)])

    payload = await fill_block(
        llm, a_skill_registry(), a_segment(0), a_planned_block(block_type), duration_ms=MEASURED_MS
    )

    assert llm.calls[0].schema is block_schema_for(block_type)
    assert block_type.value in llm.calls[0].prompt
    # And what comes back validates against that same schema -- the round trip through the
    # untyped dict Segment.scene stores it as (D29).
    assert block_schema_for(block_type).model_validate(payload)


async def test_the_measured_duration_reaches_the_prompt_in_seconds() -> None:
    """The pack's density rules are thresholds in seconds ("under 12 seconds", "12 to 30
    seconds"), so milliseconds in the prompt would be a unit the model has to convert itself."""
    llm = FakeLLMProvider([a_payload_for(BlockType.TEXT_PANEL)])

    await fill_block(
        llm,
        a_skill_registry(),
        a_segment(0),
        a_planned_block(BlockType.TEXT_PANEL),
        duration_ms=21_000,
    )

    assert "21.0 seconds" in llm.calls[0].prompt
    assert "21000" not in llm.calls[0].prompt


async def test_the_narration_the_scene_accompanies_reaches_the_prompt() -> None:
    """The pack's last section is entirely about not contradicting the narration and never
    inventing a number it does not supply -- which is unenforceable if the narration is not sent."""
    llm = FakeLLMProvider([a_payload_for(BlockType.TEXT_PANEL)])
    segment = a_segment(0).model_copy(
        update={"narration": "A parameterised query keeps the value a value."}
    )

    await fill_block(
        llm,
        a_skill_registry(),
        segment,
        a_planned_block(BlockType.TEXT_PANEL),
        duration_ms=MEASURED_MS,
    )

    assert "A parameterised query keeps the value a value." in llm.calls[0].prompt
