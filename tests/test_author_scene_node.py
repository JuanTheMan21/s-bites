"""``core/graph/nodes/scene_author.py::author_scene`` -- the node, tested through a one-node
graph, because what it adds on top of ``fill_block`` (tested in ``test_scene_author.py``) is a
state update and two refusals, both of which are about the node rather than the call.
"""

import pytest

from core.block_types import BlockType
from core.scene_schemas import ComposedScene
from tests.block_examples import EXAMPLES
from tests.fakes import FakeLLMProvider
from tests.scene_author_fixtures import (
    MEASURED_MS,
    a_context,
    a_payload_for,
    a_planned_block,
    a_planned_segment,
    a_skill_registry,
    run_author_scene,
)
from tests.segment_examples import a_segment


async def test_the_node_fills_every_planned_block(tmp_path) -> None:
    segment = a_planned_segment(
        3, a_planned_block(BlockType.TEXT_PANEL), a_planned_block(BlockType.STAT_CALLOUT)
    )
    llm = FakeLLMProvider(
        [a_payload_for(BlockType.TEXT_PANEL), a_payload_for(BlockType.STAT_CALLOUT)]
    )

    authored = await run_author_scene(segment, a_context(a_skill_registry(), llm, tmp_path))

    assert set(authored) == {3}
    scene = ComposedScene.model_validate(authored[3].scene)
    assert scene.blocks[0].payload == EXAMPLES[BlockType.TEXT_PANEL]
    assert scene.blocks[1].payload == EXAMPLES[BlockType.STAT_CALLOUT]
    # Nothing measured or planned is disturbed -- this node fills block payloads and nothing else.
    assert authored[3].duration_ms == MEASURED_MS
    assert authored[3].title == segment.title


async def test_an_unmeasured_segment_raises_before_any_llm_call(tmp_path) -> None:
    """Invariant 1's last line of defence. Unreachable while ``assign_tiers``/``plan_visuals`` sit
    between this node and the TTS fan-out -- which is exactly why it is worth pinning: it is what
    makes reordering the graph fail loudly instead of authoring a scene against an invented
    duration."""
    segment = a_planned_segment(0, a_planned_block(BlockType.TEXT_PANEL)).model_copy(
        update={"duration_ms": None}
    )
    llm = FakeLLMProvider([a_payload_for(BlockType.TEXT_PANEL)])

    with pytest.raises(ValueError, match="no measured duration_ms"):
        await run_author_scene(segment, a_context(a_skill_registry(), llm, tmp_path))

    assert llm.calls == []


async def test_a_segment_with_no_scene_plan_raises_before_any_llm_call(tmp_path) -> None:
    """The T18B equivalent of the duration guard: a segment that reached this node without
    ``plan_visuals`` having run yet fails loudly rather than authoring nothing."""
    segment = a_segment(0, duration_ms=MEASURED_MS)
    llm = FakeLLMProvider([a_payload_for(BlockType.TEXT_PANEL)])

    with pytest.raises(ValueError, match="no scene plan"):
        await run_author_scene(segment, a_context(a_skill_registry(), llm, tmp_path))

    assert llm.calls == []
