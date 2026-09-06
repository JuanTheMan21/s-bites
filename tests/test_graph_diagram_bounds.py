"""T18K/D163: ``GraphDiagramSlots``'s "Three to seven nodes" (and the edge/traversal caps) were
prose only, with nothing actually enforced -- a real render showed a congested, crossing-lines
diagram with no cap catching it before render. Enforced via ``model_validator``, not
``Field(min_length=..., max_length=...)`` -- see ``core/block_schemas_graph.py``'s own top-of-file
note for why a ``Field`` constraint would be rejected by Azure strict mode outright rather than
merely unenforced.
"""

import pytest
from pydantic import ValidationError

from core.block_schemas_graph import GraphDiagramSlots, GraphEdge, GraphNode, GraphTraversalStep

HEADLINE = "h"


def _node(i: int) -> GraphNode:
    return GraphNode(id=f"n{i}", label=f"Node {i}", caption=None, anchor_phrase=f"node {i}")


def _payload(node_count: int, *, edge_count: int = 0, traversal_count: int = 0) -> dict:
    nodes = [_node(i) for i in range(node_count)]
    edges = [
        GraphEdge(from_id="n0", to_id="n0", label=None).model_dump() for _ in range(edge_count)
    ]
    traversal = [
        GraphTraversalStep(anchor_phrase=f"step {i}", node_id="n0").model_dump()
        for i in range(traversal_count)
    ]
    return {
        "headline": HEADLINE,
        "layout": "graph",
        "nodes": [n.model_dump() for n in nodes],
        "edges": edges,
        "positions": [],
        "traversal": traversal,
    }


@pytest.mark.parametrize("node_count", [3, 5, 7])
def test_node_counts_inside_the_bound_validate(node_count: int) -> None:
    GraphDiagramSlots.model_validate(_payload(node_count))


@pytest.mark.parametrize("node_count", [0, 1, 2, 8, 9, 30])
def test_node_counts_outside_the_bound_raise(node_count: int) -> None:
    with pytest.raises(ValidationError, match="nodes must have 3 to 7 entries"):
        GraphDiagramSlots.model_validate(_payload(node_count))


def test_too_many_edges_raises() -> None:
    with pytest.raises(ValidationError, match="edges must have at most 12 entries"):
        GraphDiagramSlots.model_validate(_payload(3, edge_count=13))


def test_too_many_traversal_steps_raises() -> None:
    with pytest.raises(ValidationError, match="traversal must have at most 8 entries"):
        GraphDiagramSlots.model_validate(_payload(3, traversal_count=9))


def test_the_bound_is_a_model_validator_not_a_json_schema_keyword() -> None:
    """The actual K3 correction: a Field(min_length=..., max_length=...) here would be REJECTED
    by Azure strict mode with a 400 at call time (core/strict_schema.py's own documented
    constraint), not merely unenforced -- so the bound must never surface as minItems/maxItems in
    the generated JSON schema."""
    generated = GraphDiagramSlots.model_json_schema()
    nodes_schema = generated["properties"]["nodes"]
    assert "minItems" not in nodes_schema
    assert "maxItems" not in nodes_schema
