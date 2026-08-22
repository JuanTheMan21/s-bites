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

from core.frame_budget import scale_frame_budget
from core.models import (
    DEFAULT_TARGET_DURATION_MS,
    MIN_SEGMENTS,
    SECONDS_PER_SEGMENT,
    Importance,
    JobStatus,
    Segment,
    Tier,
    VideoJob,
    VisualIntent,
)
from core.outline_schema import Outline, SegmentPlan
from core.slot_schemas import SLOT_SCHEMAS, slot_schema_for
from core.strict_schema import StrictSchema
from core.tier_resolver import TierAssignment, TierPlan, resolve_tiers

__all__ = [
    "DEFAULT_TARGET_DURATION_MS",
    "MIN_SEGMENTS",
    "SECONDS_PER_SEGMENT",
    "SLOT_SCHEMAS",
    "Importance",
    "JobStatus",
    "Outline",
    "Segment",
    "SegmentPlan",
    "StrictSchema",
    "Tier",
    "TierAssignment",
    "TierPlan",
    "VideoJob",
    "VisualIntent",
    "resolve_tiers",
    "scale_frame_budget",
    "slot_schema_for",
]
