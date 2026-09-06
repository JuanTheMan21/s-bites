"""T18M: persist a failed composition attempt's own scene and findings, so a segment that
exhausts every recovery step in ``render_scene.py`` is diagnosable afterward instead of leaving
only bare finding codes on ``RenderOutcome`` -- the gap that made segments 4 and 12 of job
``eaebea14d7484ef19a82fcd7881f94d3`` undiagnosable even though they got the full 3 attempts.

Split out of ``render_scene.py`` rather than inlined: that module was already at 181 of its
200-line ceiling, and this is a genuinely separate concern -- what the pipeline records for
POST-HOC diagnosis, not what it does to keep rendering moving.
"""

import json
import logging

from core.models import Segment
from core.scene_schemas import ComposedScene
from interfaces import AdapterError, Storage

logger = logging.getLogger(__name__)

FAILED_SCENE_KEY = "{job_id}/segments/{index}/failed_scene_attempt{attempt}.json"


async def save_failed_attempt(
    storage: Storage,
    job_id: str,
    segment: Segment,
    scene: ComposedScene,
    findings: list[str],
    *,
    attempt: int,
) -> None:
    """Write the scene that just failed geometry validation, plus the raw findings that failed
    it, to ``Storage``. Best-effort: a diagnostic write must never fail the render it is trying
    to help diagnose, so any ``Storage`` failure here is logged and swallowed, not raised."""
    key = FAILED_SCENE_KEY.format(job_id=job_id, index=segment.index, attempt=attempt)
    payload = json.dumps({"scene": scene.model_dump(), "findings": findings}, indent=2)
    try:
        await storage.put_bytes(key, payload.encode("utf-8"), content_type="application/json")
    except AdapterError as exc:
        logger.warning(
            "segment %s: failed to persist diagnostic for attempt %s -- %s",
            segment.index,
            attempt,
            exc,
        )
