"""``core/graph/nodes/collect_scenes.py`` -- the join between ``author_scene``'s fan-out and
``render_scene``'s, which T18I gave a real job: applying the whole-video annotation budget
(``core/annotation_normalize.py::cap_video_annotation_budget``) once every segment's own
annotations exist, the only point in the pipeline that can see them all at once."""

from core.block_types import AnnotationTargetKind, AnnotationType, BlockType, MotifName, SceneLayout
from core.graph.nodes.collect_scenes import collect_scenes
from core.scene_schemas import ComposedAnnotation, ComposedBlock, ComposedScene
from tests.segment_examples import a_segment


def _scene(annotations: list[ComposedAnnotation]) -> ComposedScene:
    return ComposedScene(
        motif=MotifName.TERMINAL,
        layout=SceneLayout.SINGLE,
        blocks=[ComposedBlock(block_type=BlockType.TEXT_PANEL, role="role", anchor_phrase=None)],
        continues_previous=False,
        annotations=annotations,
    )


def _mark() -> ComposedAnnotation:
    return ComposedAnnotation(
        annotation_type=AnnotationType.CHECK,
        target_block_index=0,
        target_kind=AnnotationTargetKind.ITEM,
        target_item_index=0,
        anchor_phrase="a phrase",
        caption=None,
    )


async def test_no_update_returned_when_nothing_needs_capping() -> None:
    segments = {
        0: a_segment(0).model_copy(update={"scene": _scene([]).model_dump()}),
        1: a_segment(1).model_copy(update={"scene": _scene([_mark()]).model_dump()}),
    }
    result = await collect_scenes({"segments": segments})
    assert result == {}


async def test_over_budget_segments_are_cleared() -> None:
    """Five annotated non-title segments, a 40% budget -> only the first two survive; the join
    returns updates for exactly the segments that changed."""
    segments = {
        0: a_segment(0).model_copy(update={"scene": _scene([]).model_dump()}),
        1: a_segment(1).model_copy(update={"scene": _scene([_mark()]).model_dump()}),
        2: a_segment(2).model_copy(update={"scene": _scene([_mark()]).model_dump()}),
        3: a_segment(3).model_copy(update={"scene": _scene([_mark()]).model_dump()}),
        4: a_segment(4).model_copy(update={"scene": _scene([]).model_dump()}),
        5: a_segment(5).model_copy(update={"scene": _scene([]).model_dump()}),
    }
    result = await collect_scenes({"segments": segments})
    updated = result["segments"]
    assert set(updated) == {3}
    assert ComposedScene.model_validate(updated[3].scene).annotations == []
    # Untouched segments are absent from the update entirely, not returned unchanged.
    assert 1 not in updated
    assert 2 not in updated
