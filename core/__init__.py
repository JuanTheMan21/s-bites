"""Business logic and the domain vocabulary it is written in.

Nothing here may import an adapter or a vendor SDK -- ``core/`` calls the contracts in
``interfaces/`` and ``config.py`` chooses who answers. The orchestration library is the single
exception, and only under ``core/graph/``. A ``PreToolUse`` hook enforces both.

Prose here deliberately avoids naming that library: CLAUDE.md's boundary check is a plain text
grep over this package, and a mention in a docstring is indistinguishable from an import to it.

The dependency runs one way: ``core`` imports ``interfaces``, never the reverse (D22). The
contracts' own vocabulary -- ``SkillPack``, ``QueuedJob`` -- stays in ``interfaces/`` and is not
duplicated here; ``Segment``, ``VisualIntent``, ``Tier`` and ``VideoJob`` are domain concepts
and appear in no interface signature.
"""

from core.block_schemas import BLOCK_SCHEMAS, block_schema_for
from core.block_types import ALLOWED_BLOCKS, BlockType, MotifName, SceneLayout
from core.frame_budget import scale_frame_budget
from core.models import (
    DEFAULT_TARGET_DURATION_MS,
    MIN_SEGMENTS,
    SECONDS_PER_SEGMENT,
    Importance,
    Segment,
    Tier,
    VisualIntent,
)
from core.outline_schema import Outline, SegmentPlan
from core.scene_plan_schema import PlannedBlock, SegmentScenePlan, VideoScenePlan
from core.scene_schemas import ComposedBlock, ComposedScene
from core.strict_schema import StrictSchema
from core.synthesis import SynthesisResult, WordMark
from core.tier_resolver import TierAssignment, TierPlan, resolve_tiers
from core.video_job import JobStatus, VideoJob

__all__ = [
    "ALLOWED_BLOCKS",
    "BLOCK_SCHEMAS",
    "DEFAULT_TARGET_DURATION_MS",
    "MIN_SEGMENTS",
    "SECONDS_PER_SEGMENT",
    "BlockType",
    "ComposedBlock",
    "ComposedScene",
    "Importance",
    "JobStatus",
    "MotifName",
    "Outline",
    "PlannedBlock",
    "SceneLayout",
    "Segment",
    "SegmentPlan",
    "SegmentScenePlan",
    "StrictSchema",
    "SynthesisResult",
    "Tier",
    "TierAssignment",
    "TierPlan",
    "VideoJob",
    "VideoScenePlan",
    "VisualIntent",
    "WordMark",
    "block_schema_for",
    "resolve_tiers",
    "scale_frame_budget",
]
