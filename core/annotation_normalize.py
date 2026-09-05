"""Enforcing ``runtime_skills/annotation-authoring``'s own stated rules in code, the same move
``core/scene_variety.py`` makes for the visual plan and for the same reason: the skill pack has
said "at most one or two annotations per scene, most scenes should have none" since T18C, and a
real render still showed it firing inconsistently -- one sentence marked, the next not, for no
visible reason. Prose asked for restraint; nothing checked whether the model actually gave it.

Also enforces a shape the skill pack does not (and structurally cannot) ask for in words: when a
scene marks more than one item on the SAME diagram with CURSOR, the marks must walk the diagram
in the order the narration does. A cursor that lands on node 2, then node 0, reads as random even
though each individual placement is correct -- coherence is a property of the *set*, which no
single-annotation authoring rule can express.
"""

import itertools

from core.block_types import AnnotationTargetKind, AnnotationType
from core.scene_schemas import ComposedAnnotation

# The skill pack's own stated ceiling, verbatim ("at most one or two annotations per scene").
_MAX_ANNOTATIONS_PER_SCENE = 2

# T18I: the skill pack's OTHER stated rule -- "most scenes should have none at all" -- has no
# per-scene mechanism to enforce it (a scene is authored alone, with no view of how many of its
# siblings already used one). Enforced instead as a whole-video budget once every segment's
# annotations exist: at most this fraction of non-title segments may carry any annotation, so
# "most" stays true as a fact about the video, not a hope about each scene -- the same
# structural move ``core/scene_variety.py`` makes for block-type variety, applied one level down.
_MAX_ANNOTATED_FRACTION = 0.4


def cap_video_annotation_budget(
    annotations_by_segment: dict[int, list[ComposedAnnotation]],
) -> dict[int, list[ComposedAnnotation]]:
    """Clear every segment's annotations once the whole video's own annotated-segment count
    exceeds its budget -- kept segments are the EARLIEST ones with annotations, in index order,
    a simple and deterministic tie-break rather than a judgment call about which scene's
    annotation matters more (this module has no basis to make that call)."""
    annotated = sorted(index for index, marks in annotations_by_segment.items() if marks)
    total = len(annotations_by_segment)
    # max(1, ...): a very short video (or a test fixture with one real segment) can never keep
    # a single annotated segment under 40% of itself -- the same floor core/scene_variety.py's
    # own fraction check applies, for the same reason. Meaningless when total is 0 (annotated is
    # then always empty too, so the comparison below never engages the floor).
    budget = max(1, int(total * _MAX_ANNOTATED_FRACTION))
    if len(annotated) <= budget:
        return annotations_by_segment

    keep = set(annotated[:budget])
    return {
        index: (marks if index in keep else []) for index, marks in annotations_by_segment.items()
    }


def _is_coherent_walk(cursors: list[ComposedAnnotation]) -> bool:
    """True if these CURSOR annotations, in the order authored, target strictly increasing item
    indices on their shared block -- a walk that visits nodes in the order the narration reaches
    them. Authored order is narration order (the model is given the narration once, top to
    bottom), so this does not need each annotation's own resolved anchor time to check."""
    indices = [c.target_item_index for c in cursors]
    return all(a < b for a, b in itertools.pairwise(indices))


def normalize_annotations(annotations: list[ComposedAnnotation]) -> list[ComposedAnnotation]:
    """Cap density and drop any CURSOR group that does not walk its target coherently.

    Order-preserving throughout: capping keeps the first ``_MAX_ANNOTATIONS_PER_SCENE`` as
    authored (the model's own narration-order priority) rather than picking a "best" subset,
    which this module has no way to judge. Dropping an incoherent CURSOR group removes every
    annotation in it -- a partially-fixed walk (drop just the one out-of-order mark) can still
    read as skipping a node, which is the same complaint in a different shape.
    """
    kept = annotations[:_MAX_ANNOTATIONS_PER_SCENE]

    # Grouped by (block, target_kind), not block alone: ITEM and LINK are independently-numbered
    # lists on the same block (core/block_items.py -- a GRAPH_DIAGRAM's nodes and its edges are
    # two different index spaces), so an ITEM cursor at index 0 and a LINK cursor at index 1 are
    # not "out of order" with each other at all -- they aren't even comparable. Caught live, not
    # guessed: project-reviewer, confirmed it silently dropped two independently-valid
    # annotations that happened to cross-space "decrease".
    cursors_by_target: dict[tuple[int, AnnotationTargetKind], list[ComposedAnnotation]] = {}
    for annotation in kept:
        if annotation.annotation_type == AnnotationType.CURSOR:
            key = (annotation.target_block_index, annotation.target_kind)
            cursors_by_target.setdefault(key, []).append(annotation)

    incoherent_targets = {
        target
        for target, cursors in cursors_by_target.items()
        if len(cursors) > 1 and not _is_coherent_walk(cursors)
    }
    if not incoherent_targets:
        return kept

    return [
        annotation
        for annotation in kept
        if not (
            annotation.annotation_type == AnnotationType.CURSOR
            and (annotation.target_block_index, annotation.target_kind) in incoherent_targets
        )
    ]
