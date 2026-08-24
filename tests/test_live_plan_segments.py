"""The real proof T15's DoD asks for: skill packs "demonstrably change behaviour" against a real
model, not just reach the prompt (that half is pinned offline in ``tests/test_plan_segments.py``).

``core/graph/nodes/outline.py::generate_outline`` and ``.../scripting.py::write_narration``
against the real ``AzureOpenAILLMProvider`` and the real, disk-backed ``DiskSkillRegistry`` reading
the actual ``runtime_skills/outline/1.0.md`` / ``scripting/1.0.md`` / ``house-style/1.0.md`` files
-- these have never been sent to a live model before this task. Costs one outline completion plus
one per segment (a small job here, so a handful of completions) -- a fraction of a cent.
"""

from pathlib import Path

import pytest

from adapters.azure.llm_provider import AzureOpenAILLMProvider
from adapters.local.skill_registry import DiskSkillRegistry
from core.graph.nodes.outline import generate_outline
from core.graph.nodes.scripting import write_narration
from core.models import VideoJob
from tests.azure_live import require

pytestmark = pytest.mark.live

# 84s targets 3 segments (round(84_000 / 1000 / 28) == 3) -- enough to see the packs apply
# consistently across more than one call without spending much money.
TARGET_DURATION_MS = 84_000

# The scripting pack's "no formatting" rule, checked as literally as a live test safely can:
# these are the artifacts a voice could never read, not phrasing this test would have to guess at.
FORBIDDEN_MARKDOWN = ("**", "##", "\n-", "\n*")


def _provider() -> AzureOpenAILLMProvider:
    return AzureOpenAILLMProvider(
        endpoint=require("AZURE_OPENAI_ENDPOINT"),
        api_key=require("AZURE_OPENAI_API_KEY"),
        deployment=require("AZURE_OPENAI_DEPLOYMENT"),
        api_version=require("AZURE_OPENAI_API_VERSION"),
    )


def _skills() -> DiskSkillRegistry:
    return DiskSkillRegistry(Path(__file__).resolve().parent.parent / "runtime_skills")


async def test_the_real_packs_produce_a_narrated_outline_for_a_real_topic() -> None:
    job = VideoJob(job_id="live-t15", topic="SQL injection", target_duration_ms=TARGET_DURATION_MS)
    llm = _provider()
    try:
        segments = await generate_outline(llm, _skills(), job)
        assert segments, "an outline with no segments would validate and be useless"

        narrated = await write_narration(llm, _skills(), segments)
    finally:
        await llm.aclose()

    assert len(narrated) == len(segments)
    for segment in narrated.values():
        assert segment.narration
        for artifact in FORBIDDEN_MARKDOWN:
            assert artifact not in segment.narration, (
                f"segment {segment.index}'s narration contains {artifact!r} -- the scripting "
                "pack's 'no formatting' rule isn't landing; consider a runtime_skills/scripting/"
                "1.1.md"
            )
        word_count = len(segment.narration.split())
        # Loose on purpose -- this is a live model's word count, not a deterministic one. Wide
        # enough not to be flaky, tight enough to catch the pack's ~70-80-word target being
        # ignored outright (a one-sentence answer, or a multi-paragraph one).
        assert 30 <= word_count <= 150, (
            f"segment {segment.index}'s narration is {word_count} words -- the scripting pack's "
            "~70-80-word target isn't landing even loosely; consider a runtime_skills/scripting/"
            "1.1.md"
        )
