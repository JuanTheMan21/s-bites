"""Every LLM-facing schema, checked against Azure strict mode before Azure ever sees it.

Renamed from ``tests/test_slot_schemas.py`` (T18B): schemas are keyed by ``BlockType`` now, and
this file also covers the new ``core.scene_plan_schema`` classes (``PlannedBlock``,
``SegmentScenePlan``, ``VideoScenePlan``) -- they inherit ``StrictSchema`` too, so the recursive
conformance walk already covers them by construction, but a coverage gap there would be just as
costly (a 400 minutes into a real run) as one in a block schema.

Strict mode rejects an unsupported schema with a 400 at call time, so the cost of getting this
wrong is a failed run, minutes in, pointing at the adapter rather than at the schema. These tests
move that failure to ``pytest``.

The conformance test enumerates ``StrictSchema`` subclasses recursively rather than reading a
list, so a schema added later is covered by virtue of existing. That is the point of the marker
base class -- a registry someone has to remember to update is a registry that goes stale.
"""

from typing import Any

import pytest

from core import StrictSchema
from core.block_schemas import BLOCK_SCHEMAS, DiagramNode, block_schema_for
from core.block_types import BlockType
from core.models import Segment, VisualIntent
from core.scene_schemas import ComposedBlock, ComposedScene
from tests.block_examples import EXAMPLES

# Keywords Azure strict mode does not accept. Reaching for one of these is the natural way to
# say "a headline should be short", and it is exactly what turns a schema into a 400.
UNSUPPORTED_KEYWORDS = {
    "minLength",
    "maxLength",
    "pattern",
    "format",
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "multipleOf",
    "minItems",
    "maxItems",
    "uniqueItems",
    "minProperties",
    "maxProperties",
    "patternProperties",
    "propertyNames",
    "default",
}

# Sub-objects keyed by author-chosen names. Their keys are field names, not schema keywords, so
# a slot field legitimately called "format" must not read as a violation.
NAME_KEYED = {"properties", "$defs"}


def all_strict_schemas() -> list[type[StrictSchema]]:
    """Every LLM-facing model, however deeply subclassed."""
    found: dict[str, type[StrictSchema]] = {}
    stack = list(StrictSchema.__subclasses__())
    while stack:
        cls = stack.pop()
        if cls.__name__ not in found:
            found[cls.__name__] = cls
            stack.extend(cls.__subclasses__())
    return sorted(found.values(), key=lambda c: c.__name__)


def object_nodes(schema: dict[str, Any]) -> list[dict[str, Any]]:
    """The schema itself, plus every ``$defs`` entry that describes an object.

    Enums land in ``$defs`` too and are not objects, so ``additionalProperties`` does not apply
    to them -- filtering on ``properties`` is what keeps the assertions honest.
    """
    return [schema, *(d for d in schema.get("$defs", {}).values() if "properties" in d)]


def keywords_in(node: Any) -> set[str]:
    """Unsupported keywords anywhere in the schema tree, ignoring author-chosen field names."""
    found: set[str] = set()
    if isinstance(node, dict):
        found |= set(node) & UNSUPPORTED_KEYWORDS
        for key, value in node.items():
            children = value.values() if key in NAME_KEYED and isinstance(value, dict) else [value]
            for child in children:
                found |= keywords_in(child)
    elif isinstance(node, list):
        for item in node:
            found |= keywords_in(item)
    return found


def test_every_block_type_has_a_block_schema() -> None:
    """T18B's version of T4's definition of done. A missing entry surfaces at scene-authoring
    time otherwise."""
    assert set(BLOCK_SCHEMAS) == set(BlockType)


def test_no_block_schema_is_registered_against_a_dead_block_type() -> None:
    for block_type, schema in BLOCK_SCHEMAS.items():
        assert isinstance(block_type, BlockType)
        assert issubclass(schema, StrictSchema)


def test_the_schemas_found_include_the_ones_we_expect() -> None:
    """Guards the enumeration itself -- a walker that finds nothing passes every test below."""
    names = {c.__name__ for c in all_strict_schemas()}
    assert {"SegmentPlan", "Outline", "DiagramNode", "PlannedBlock", "VideoScenePlan"} <= names
    assert {c.__name__ for c in BLOCK_SCHEMAS.values()} <= names


@pytest.mark.parametrize("schema", all_strict_schemas(), ids=lambda c: c.__name__)
def test_schema_satisfies_azure_strict_mode(schema: type[StrictSchema]) -> None:
    generated = schema.model_json_schema()

    leaked = keywords_in(generated)
    assert not leaked, f"{schema.__name__} uses keywords strict mode rejects: {sorted(leaked)}"

    for node in object_nodes(generated):
        title = node.get("title", schema.__name__)
        assert node.get("type") == "object", f"{title} is not an object"
        assert node.get("additionalProperties") is False, f"{title} allows extra properties"
        missing = set(node.get("properties", {})) - set(node.get("required", []))
        assert not missing, (
            f"{title}: {sorted(missing)} not required. Strict mode requires every property, and "
            "pydantic drops a field from `required` as soon as it has a default -- express "
            "optionality as `X | None` with no default instead."
        )


@pytest.mark.parametrize("schema", all_strict_schemas(), ids=lambda c: c.__name__)
def test_every_field_carries_a_description(schema: type[StrictSchema]) -> None:
    """Descriptions are the only guidance channel strict mode leaves open."""
    for name, field in schema.model_json_schema()["properties"].items():
        assert field.get("description"), f"{schema.__name__}.{name} has no description"


@pytest.mark.parametrize("block_type", list(BlockType), ids=lambda b: b.value)
def test_a_realistic_payload_validates_for_every_block_type(block_type: BlockType) -> None:
    payload = block_schema_for(block_type).model_validate(EXAMPLES[block_type])
    assert payload.model_dump() == EXAMPLES[block_type]


@pytest.mark.parametrize("block_type", list(BlockType), ids=lambda b: b.value)
def test_a_filled_payload_round_trips_through_a_segment(block_type: BlockType) -> None:
    """``Segment.scene`` is an untyped dict; ``block_schema_for`` gives a block's payload back
    its type."""
    scene = ComposedScene(
        motif="terminal",
        layout="single",
        blocks=[
            ComposedBlock(
                block_type=block_type, role="role", anchor_phrase=None, payload=EXAMPLES[block_type]
            )
        ],
        continues_previous=False,
    )
    segment = Segment(
        index=0,
        title="t",
        summary="s",
        visual_intent=VisualIntent.BULLET_LIST,
        importance=3,
        scene=scene.model_dump(),
    )
    restored = Segment.model_validate_json(segment.model_dump_json())
    restored_scene = ComposedScene.model_validate(restored.scene)
    assert block_schema_for(restored_scene.blocks[0].block_type).model_validate(
        restored_scene.blocks[0].payload
    )


def test_a_nested_model_is_itself_strict() -> None:
    """The case a top-level-only check would miss: a nested model that forgot the base class."""
    assert issubclass(DiagramNode, StrictSchema)
    assert DiagramNode.model_json_schema()["additionalProperties"] is False
