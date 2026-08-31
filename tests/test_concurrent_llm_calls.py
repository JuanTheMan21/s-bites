"""E7 (T18E, D121/D122): two call sites that used to be sequential now issue their per-item LLM
calls concurrently via ``asyncio.gather`` -- ``core/graph/nodes/scene_author.py::author_scene``'s
per-block ``fill_block`` calls, and ``core/graph/nodes/scripting.py::write_narration``'s
per-segment loop (D47's original "no measured reason yet" stance, reopened explicitly).

A fake with no real suspension point can't distinguish ``asyncio.gather`` from a sequential loop
-- both produce byte-identical call order and timing against a fake that always resolves
synchronously (``tests/fakes/llm_provider.py::FakeLLMProvider`` among them). This module's own
``ConcurrencyProbeLLMProvider`` adds one genuine suspension point per call (``asyncio.sleep(0)``)
so overlapping calls actually interleave, and records the peak number in flight -- 1 proves
sequential, more than 1 proves real concurrency.
"""

import asyncio
from typing import Any

from pydantic import BaseModel

from core.block_types import BlockType
from core.graph.nodes.scripting import write_narration
from core.scripting_schema import Narration
from interfaces import LLMProvider, SkillPack
from interfaces.llm_provider import T
from tests.fakes import FakeSkillRegistry
from tests.scene_author_fixtures import (
    a_context,
    a_payload_for,
    a_planned_block,
    a_planned_segment,
    a_skill_registry,
    no_annotations,
    run_author_scene,
)
from tests.segment_examples import a_segment


class ConcurrencyProbeLLMProvider(LLMProvider):
    """Answers from a queue, like ``FakeLLMProvider``, but with one genuine suspension point per
    call so real concurrency and a sequential loop produce observably different peak in-flight
    counts. Not type-differentiated on response pop -- callers here only ever queue one schema
    per test, so ``FakeLLMProvider``'s isinstance check isn't needed."""

    def __init__(self, responses: list[BaseModel]) -> None:
        self.responses = list(responses)
        self.in_flight = 0
        self.peak_in_flight = 0

    async def generate(self, prompt: str, schema: type[T], *, system: str | None = None) -> Any:
        self.in_flight += 1
        self.peak_in_flight = max(self.peak_in_flight, self.in_flight)
        await asyncio.sleep(0)
        response = self.responses.pop(0)
        self.in_flight -= 1
        return response


async def test_fill_block_calls_within_one_scene_run_concurrently(tmp_path) -> None:
    segment = a_planned_segment(
        0, a_planned_block(BlockType.TEXT_PANEL), a_planned_block(BlockType.STAT_CALLOUT)
    )
    llm = ConcurrencyProbeLLMProvider(
        [
            a_payload_for(BlockType.TEXT_PANEL),
            a_payload_for(BlockType.STAT_CALLOUT),
            no_annotations(),
        ]
    )

    await run_author_scene(segment, a_context(a_skill_registry(), llm, tmp_path))

    assert llm.peak_in_flight >= 2


async def test_write_narration_calls_across_segments_run_concurrently() -> None:
    segments = {i: a_segment(i) for i in range(3)}
    llm = ConcurrencyProbeLLMProvider([Narration(text=f"Narration {i}.") for i in range(3)])
    skills = FakeSkillRegistry(
        [
            SkillPack(name="scripting", version="1.0", content="SCRIPTING PACK"),
            SkillPack(name="house-style", version="1.0", content="HOUSE STYLE PACK"),
        ]
    )

    narrated = await write_narration(llm, skills, segments)

    assert llm.peak_in_flight >= 2
    assert len(narrated) == 3
