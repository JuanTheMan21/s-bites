"""The safe fallback a segment's render lands on once a re-authored scene (``scene_reauthor.py``)
still fails geometry validation, or the finding wasn't content-shaped to begin with (``rendering/
geometry_findings.py::is_content_retryable``).

T18I: per-segment isolation for the production failure story -- one bad segment used to kill the
whole ``VideoJob`` (``core/graph/nodes/render_scene.py``'s own exception propagating through the
graph). A plain title card is geometry-safe by construction (it is what every segment 0 already
renders, and TITLE is the simplest block in the library) and needs no LLM call, so it costs
nothing and cannot itself trigger the same failure -- a degraded segment is a title card, never a
hole in the finished video.
"""

from core.block_schemas import TitleSlots
from core.block_types import BlockType, MotifName, SceneLayout
from core.models import Segment
from core.scene_schemas import ComposedBlock, ComposedScene


def title_card_scene(segment: Segment, motif: MotifName) -> ComposedScene:
    """A single, geometry-safe TITLE block built deterministically from ``segment``'s own
    ``title``/``summary`` -- no ``LLMProvider`` call, so this cannot itself fail the way the
    scene it is replacing did."""
    payload = TitleSlots(headline=segment.title, subtitle=segment.summary, key_terms=[])
    return ComposedScene(
        motif=motif,
        layout=SceneLayout.SINGLE,
        blocks=[
            ComposedBlock(
                block_type=BlockType.TITLE,
                role="Fallback content after a render failure",
                anchor_phrase=None,
                payload=payload.model_dump(),
            )
        ],
        continues_previous=False,
    )
