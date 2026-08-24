"""The scripting call: one ``LLMProvider.generate`` per segment producing
``core.scripting_schema.Narration``, from the ``scripting`` pack and the ``house-style`` pack
it is always interpolated alongside."""

from core.graph.nodes.skill_prompt import load_step_prompt
from core.graph.nodes.structured_retry import generate_with_bounded_retries
from core.models import Segment
from core.scripting_schema import Narration
from interfaces import LLMProvider, SkillRegistry

SCRIPTING_PACK = "scripting"


async def write_narration(
    llm: LLMProvider, skills: SkillRegistry, segments: dict[int, Segment]
) -> dict[int, Segment]:
    """Narrate every segment.

    Sequential, not concurrent -- these are the same shape of call T9's adapter already
    rate-limits internally, and there is no measured reason yet to add node-level concurrency on
    top of that (D47's "measure before optimizing").
    """
    step_prompt = await load_step_prompt(skills, SCRIPTING_PACK)
    narrated: dict[int, Segment] = {}
    for index, segment in segments.items():
        prompt = (
            f"{step_prompt.step}\n\n"
            f"Segment title: {segment.title}\n"
            f"What this segment teaches: {segment.summary}\n"
            f"On-screen visual: {segment.visual_intent.value}"
        )
        narration = await generate_with_bounded_retries(
            llm, prompt, Narration, system=step_prompt.house_style
        )
        narrated[index] = segment.model_copy(update={"narration": narration.text})
    return narrated
