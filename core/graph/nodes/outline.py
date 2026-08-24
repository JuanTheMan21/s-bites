"""The outline call: one ``LLMProvider.generate`` producing ``core.outline_schema.Outline``,
from the ``outline`` pack and the ``house-style`` pack it is always interpolated alongside."""

from core.graph.nodes.skill_prompt import load_step_prompt
from core.graph.nodes.structured_retry import generate_with_bounded_retries
from core.models import Segment, VideoJob
from core.outline_schema import Outline
from interfaces import LLMProvider, SkillRegistry

OUTLINE_PACK = "outline"


async def generate_outline(
    llm: LLMProvider, skills: SkillRegistry, job: VideoJob
) -> dict[int, Segment]:
    """Ask for ``job.segment_count`` segments and return them unnarrated, indexed from 0.

    Nothing here enforces that the model returned exactly that many -- Azure strict mode has no
    length keyword to hold it to (D26), and nothing downstream (the ``Send`` fan-out, the tier
    resolver) requires an exact count. The prompt states the derived count per T4's flag; it is
    a target for the model, not an invariant this function checks.
    """
    step_prompt = await load_step_prompt(skills, OUTLINE_PACK)
    prompt = (
        f"{step_prompt.step}\n\nTopic: {job.topic!r}\nProduce exactly {job.segment_count} segments."
    )
    outline = await generate_with_bounded_retries(
        llm, prompt, Outline, system=step_prompt.house_style
    )
    return {index: plan.to_segment(index) for index, plan in enumerate(outline.segments)}
