"""``core.graph.nodes.skill_prompt``: loading a step pack alongside house-style."""

import pytest

from core.graph.nodes.skill_prompt import load_step_prompt
from interfaces import SkillPack, SkillPackNotFound
from tests.fakes import FakeSkillRegistry


def _registry() -> FakeSkillRegistry:
    return FakeSkillRegistry(
        [
            SkillPack(name="outline", version="1.0", content="OUTLINE CONTENT"),
            SkillPack(name="house-style", version="1.0", content="HOUSE STYLE CONTENT"),
        ]
    )


async def test_loads_the_named_step_pack_and_house_style() -> None:
    result = await load_step_prompt(_registry(), "outline")

    assert result.step == "OUTLINE CONTENT"
    assert result.house_style == "HOUSE STYLE CONTENT"


async def test_an_unknown_step_pack_propagates_skill_pack_not_found() -> None:
    with pytest.raises(SkillPackNotFound):
        await load_step_prompt(_registry(), "no-such-pack")
