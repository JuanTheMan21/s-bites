"""The join between ``author_scene``'s fan-out and ``render_scene``'s (``core/graph/
pipeline.py``). Structurally required so ``render_scene``'s fan-out has a converged, complete
``segments`` dict to read (every scene's blocks filled) -- not because anything here needs
computing for its own sake, until T18I gave it one real job: applying the whole-video annotation
budget (``core/annotation_normalize.py::cap_video_annotation_budget``), which cannot run any
earlier because it needs every segment's own authored annotations at once, the same reason
``plan_visuals`` (not ``author_scene``) is where block-type variety is enforced.
"""

from core.annotation_normalize import cap_video_annotation_budget
from core.graph.state import GraphState
from core.scene_schemas import ComposedScene


async def collect_scenes(state: GraphState) -> dict:
    """Cap the whole video's annotated-segment count, then return every segment unchanged
    otherwise. Segment 0 (the forced title card, never annotated) is excluded from the budget
    calculation the same way ``core/scene_variety.py`` excludes it from variety counts."""
    segments = state["segments"]
    by_segment = {
        index: ComposedScene.model_validate(segment.scene).annotations
        for index, segment in segments.items()
        if index != 0 and segment.scene is not None
    }
    capped = cap_video_annotation_budget(by_segment)

    updated: dict[int, object] = {}
    for index, marks in capped.items():
        if marks == by_segment[index]:
            continue
        scene = ComposedScene.model_validate(segments[index].scene)
        new_scene = scene.model_copy(update={"annotations": marks})
        updated[index] = segments[index].model_copy(update={"scene": new_scene.model_dump()})

    if not updated:
        return {}
    return {"segments": updated}
