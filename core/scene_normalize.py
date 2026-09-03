"""Structural enforcement of ``SegmentScenePlan.layout``'s own stated rule ("one block for
SINGLE, exactly two for SPLIT_HORIZONTAL") -- previously only a prompt sentence, not checked
anywhere. T18I: a SINGLE scene stacking multiple large blocks produced 42 ``canvas_overflow``
findings in a real render (D124's fifth, deliberately-deferred finding) -- a capacity problem no
positioning fix touches, because nothing capped how many blocks SINGLE's ``{% for block in
blocks %}`` loop (``_layout_single.html``) could iterate.

Pure and stdlib-only, like ``core/tier_resolver.py`` -- this is a decision about a scene's own
*shape*, made once, before anything renders.
"""

from core.block_types import SceneLayout
from core.scene_schemas import ComposedBlock

# SPLIT_HORIZONTAL's own template (_layout_split_horizontal.html) renders every block with
# compact=true -- a GRAPH_DIAGRAM's canvas drops from 620px to 220px in that mode -- so promoting
# a 2-block SINGLE scene there is a real, already-bounded home for the second block rather than a
# guess at a new layout.
_PROMOTABLE_BLOCK_COUNT = 2


def normalize_layout(
    layout: SceneLayout, blocks: list[ComposedBlock]
) -> tuple[SceneLayout, list[ComposedBlock]]:
    """Enforce each ``SceneLayout``'s own block-count rule, returning a layout/blocks pair that
    is always safe to compose: SINGLE gets exactly one block, SPLIT_HORIZONTAL exactly two.

    SINGLE with exactly two blocks is promoted to SPLIT_HORIZONTAL rather than truncated --
    both blocks survive, each in its own bounded panel. Any other mismatch (SINGLE with three or
    more, SPLIT_HORIZONTAL with anything but two) keeps the first N blocks a valid scene of that
    shape can hold; ``plan_visuals`` already logs nothing here because a mismatch this large is
    rare enough that silent truncation, not a crash, is the right default (the same "defensive
    default over an incomplete response" reasoning ``_fallback_scene`` already applies one level
    up).
    """
    if layout == SceneLayout.SINGLE:
        if len(blocks) == _PROMOTABLE_BLOCK_COUNT:
            return SceneLayout.SPLIT_HORIZONTAL, blocks
        return SceneLayout.SINGLE, blocks[:1]
    if layout == SceneLayout.SPLIT_HORIZONTAL:
        return SceneLayout.SPLIT_HORIZONTAL, blocks[:_PROMOTABLE_BLOCK_COUNT]
    return layout, blocks
