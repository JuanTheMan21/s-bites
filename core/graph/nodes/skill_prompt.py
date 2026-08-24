"""Loads a step-specific runtime skill pack alongside the house-style pack every LLM-facing step
interpolates next to it (``runtime_skills/house-style/1.0.md``'s own instruction: "This pack is
interpolated alongside the step-specific pack on every call").

Shared by every node under ``core/graph/nodes/`` that calls ``LLMProvider.generate``, so "which
packs, in what order" is answered once rather than re-derived per node.
"""

from dataclasses import dataclass

from interfaces import SkillRegistry

HOUSE_STYLE_PACK = "house-style"


@dataclass(frozen=True, slots=True)
class StepPrompt:
    """One step's pack content, plus the house-style pack every step gets alongside it."""

    step: str
    house_style: str


async def load_step_prompt(skills: SkillRegistry, step_pack: str) -> StepPrompt:
    """Load ``step_pack`` and ``house-style``, both at their newest version.

    Raises:
        SkillPackNotFound: either pack, or the newest version of it, does not exist.
    """
    step = await skills.load(step_pack)
    house_style = await skills.load(HOUSE_STYLE_PACK)
    return StepPrompt(step=step.content, house_style=house_style.content)
