"""``core/graph/node_timing.py::timed`` -- offline, no graph involved.

The one real risk this sub-part carries: LangGraph inspects a node callable's own signature (via
``inspect.signature``, which follows ``__wrapped__`` by default) to decide whether to inject
``Runtime[GraphContext]`` as a second positional argument. ``test_graph_pipeline.py`` is what
actually proves the wrapped nodes still work inside a real compiled graph; this file pins the
narrower, faster-to-check guarantee the wrapping itself must never lose.
"""

import inspect
import logging

import pytest

from core.graph.node_timing import timed


async def _example(state: dict, runtime: str) -> dict:
    """A stand-in node signature -- two positional params, the same shape every real node in
    core/graph/nodes/ has."""
    return {"state": state, "runtime": runtime}


async def test_the_wrapper_returns_the_wrapped_functions_result() -> None:
    wrapped = timed("example", _example)

    result = await wrapped({"a": 1}, "rt")

    assert result == {"state": {"a": 1}, "runtime": "rt"}


def test_inspect_signature_follows_through_to_the_original() -> None:
    """The load-bearing guarantee: LangGraph's own Runtime-injection detection relies on this."""
    wrapped = timed("example", _example)

    assert inspect.signature(wrapped) == inspect.signature(_example)
    assert wrapped.__wrapped__ is _example


async def test_start_and_finish_are_logged_under_the_given_name(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="core.graph.node_timing")
    wrapped = timed("example", _example)

    await wrapped({}, "rt")

    messages = [record.getMessage() for record in caplog.records]
    assert any("example" in m and "started" in m for m in messages)
    assert any("example" in m and "finished" in m for m in messages)
