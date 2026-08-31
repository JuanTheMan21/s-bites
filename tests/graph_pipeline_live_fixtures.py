"""Shared setup for ``test_graph_pipeline_live.py`` -- split out once the T18E annotations
addition pushed that file over the 200-line ceiling. Not a test module -- the same role
``tests/graph_pipeline_fixtures.py`` plays for the offline graph tests.
"""

from core.annotation_plan_schema import SceneAnnotations
from core.block_schemas import TitleSlots
from core.block_types import BlockType, MotifName, SceneLayout
from core.models import Importance, VisualIntent
from core.outline_schema import Outline, SegmentPlan
from core.scene_plan_schema import PlannedBlock, SegmentScenePlan, VideoScenePlan
from core.scripting_schema import Narration
from interfaces import SkillPack
from tests.fakes import FakeSkillRegistry
from tests.graph_pipeline_fixtures import PhaseQueueLLMProvider


def seeded_llm() -> PhaseQueueLLMProvider:
    outline = Outline(
        segments=[
            SegmentPlan(
                title="An aside",
                summary="Barely matters.",
                visual_intent=VisualIntent.TITLE_CARD,
                importance=Importance.ASIDE,
            ),
            SegmentPlan(
                title="The point",
                summary="The whole reason for the video.",
                visual_intent=VisualIntent.TITLE_CARD,
                importance=Importance.CRITICAL,
            ),
        ]
    )
    narrations = [Narration(text="Narration one."), Narration(text="Narration two.")]
    plan = VideoScenePlan(
        motif=MotifName.TERMINAL,
        segments=[
            SegmentScenePlan(
                segment_index=i,
                layout=SceneLayout.SINGLE,
                blocks=[PlannedBlock(block_type=BlockType.TITLE, role="Title", anchor_phrase=None)],
                continues_previous=False,
            )
            for i in range(2)
        ],
    )
    # T18E: author_scene now also calls author_annotations once its block is filled -- one
    # SceneAnnotations(annotations=[]) per segment. PhaseQueueLLMProvider matches by type rather
    # than strict position, which real interleaving across segments' concurrent Send tasks needs
    # (tests/graph_pipeline_fixtures.py's own module docstring has the full account).
    author_scene_calls = [
        TitleSlots(headline="Headline 0", subtitle=None),
        TitleSlots(headline="Headline 1", subtitle=None),
        SceneAnnotations(annotations=[]),
        SceneAnnotations(annotations=[]),
    ]
    return PhaseQueueLLMProvider([outline, *narrations, plan, *author_scene_calls])


def seeded_skills() -> FakeSkillRegistry:
    return FakeSkillRegistry(
        [
            SkillPack(name=name, version="1.0", content=f"{name} pack")
            for name in (
                "outline",
                "scripting",
                "visual-plan",
                "house-style",
                "scene-authoring",
                "annotation-authoring",
            )
        ]
    )
