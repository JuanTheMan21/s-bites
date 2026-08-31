"""The scripting call: one ``LLMProvider.generate`` per segment producing
``core.scripting_schema.Narration``, from the ``scripting`` pack and the ``house-style`` pack
it is always interpolated alongside."""

import asyncio

from core.graph.nodes.skill_prompt import StepPrompt, load_step_prompt
from core.graph.nodes.structured_retry import generate_with_bounded_retries
from core.models import Segment
from core.scripting_schema import Narration
from interfaces import LLMProvider, SkillRegistry

SCRIPTING_PACK = "scripting"


async def _narrate_one(
    llm: LLMProvider, step_prompt: StepPrompt, index: int, segment: Segment
) -> tuple[int, Segment]:
    prompt = (
        f"{step_prompt.step}\n\n"
        f"Segment title: {segment.title}\n"
        f"What this segment teaches: {segment.summary}\n"
        f"On-screen visual: {segment.visual_intent.value}"
    )
    narration = await generate_with_bounded_retries(
        llm, prompt, Narration, system=step_prompt.house_style
    )
    return index, segment.model_copy(update={"narration": narration.text})


async def write_narration(
    llm: LLMProvider, skills: SkillRegistry, segments: dict[int, Segment]
) -> dict[int, Segment]:
    """Narrate every segment concurrently.

    T18E, D121/D122: reopens D47's original "no measured reason yet" stance explicitly, on the
    user's own instruction -- not silently worked around. The Azure adapter's own
    ``asyncio.Semaphore`` already bounds real in-flight concurrency regardless of caller pattern
    (T9), so issuing every call at once is not more concurrent than issuing them one at a time,
    only faster to schedule.
    """
    step_prompt = await load_step_prompt(skills, SCRIPTING_PACK)
    results = await asyncio.gather(
        *(_narrate_one(llm, step_prompt, index, segment) for index, segment in segments.items())
    )
    return dict(results)
