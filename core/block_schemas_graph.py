"""``GRAPH_DIAGRAM``'s content schema. Split out of ``core/block_schemas.py`` (T18C) once the
combined file would have crossed the 200-line ceiling with every T18C block added -- one more
instance of "split by responsibility," not a new pattern.

``GRAPH_DIAGRAM`` retires ``DIAGRAM_CHAIN``: ``GraphLayoutMode.CHAIN`` reproduces the old single
straight rail exactly (positions computed by the template, never authored -- ``positions`` is
always null for ``CHAIN``); ``GraphLayoutMode.GRAPH`` places nodes on a real 2D canvas for
arbitrary topology, with an optional traversal highlight.
"""

from pydantic import Field

from core.block_types import GraphLayoutMode
from core.strict_schema import StrictSchema


class GraphNode(StrictSchema):
    """One node in a graph or chain diagram."""

    id: str = Field(
        description="A short unique id for this node within this diagram, e.g. 'n1' -- "
        "referenced by edges, positions, and traversal steps, never shown to the viewer."
    )
    label: str = Field(description="The node's own label, two or three words.")
    caption: str | None = Field(
        description="A short clarifying line under the label, or null if the label is clear "
        "on its own."
    )


class GraphEdge(StrictSchema):
    """One directed connection between two nodes."""

    from_id: str = Field(description="The id of the edge's source node.")
    to_id: str = Field(description="The id of the edge's destination node.")
    label: str | None = Field(
        description="A short weight, cost, or condition on this connection, e.g. '4', "
        "'O(log n)', 'if valid' -- shown on the edge itself. Null for a plain connection with no "
        "such fact. Never invent a number or condition the narration does not supply."
    )


class GraphNodePosition(StrictSchema):
    """One node's explicit place in the drawing area, for a topology the template's own
    automatic layout would tangle (a hub-and-spoke, a branching tree). Always empty when this
    diagram's layout is CHAIN -- chain positions are computed by the template, never authored."""

    node_id: str = Field(description="The id of the node this position is for.")
    x: float = Field(
        description="Horizontal position, 0.0 (left) to 1.0 (right) of the diagram's drawing area."
    )
    y: float = Field(
        description="Vertical position, 0.0 (top) to 1.0 (bottom) of the diagram's drawing area."
    )


class GraphTraversalStep(StrictSchema):
    """One moment the diagram highlights a node as the narration's explanation reaches it."""

    anchor_phrase: str = Field(
        description="A short phrase copied VERBATIM from this segment's narration, marking the "
        "moment traversal reaches this node."
    )
    node_id: str = Field(description="The id of the node the traversal highlight lands on.")


class GraphDiagramSlots(StrictSchema):
    """An ordered process (chain) or an arbitrary-topology graph (network, tree, hub)."""

    headline: str = Field(description="What this diagram shows. A short phrase.")
    layout: GraphLayoutMode = Field(
        description="CHAIN for a strictly linear rail, left to right in node order (a pipeline, "
        "an attack chain) -- edges must be exactly the n-1 consecutive pairs in node order, and "
        "positions must be empty. GRAPH for arbitrary topology on a 2D canvas."
    )
    nodes: list[GraphNode] = Field(description="Three to seven nodes.")
    edges: list[GraphEdge] = Field(
        description="The connections between nodes, by id. For CHAIN, exactly the n-1 "
        "consecutive pairs in node order. For GRAPH, any topology."
    )
    positions: list[GraphNodePosition] = Field(
        description="Explicit 2D position for some or all nodes, or empty to let the template "
        "place every node automatically. Always empty when layout is CHAIN."
    )
    traversal: list[GraphTraversalStep] = Field(
        description="Zero or more moments, in narration order, where the diagram highlights one "
        "node. Leave empty for a diagram that just sits there, fully revealed, once its entrance "
        "finishes."
    )
