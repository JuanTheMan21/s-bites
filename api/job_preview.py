"""Assembling a mid-run preview of a job's segments, split out of ``api/runner.py`` to stay under
the 200-line ceiling once T34's queue-receipt safety net pushed it over.
"""

from core.graph.state import GraphState
from core.video_job import VideoJob


def assemble_preview(values: GraphState) -> VideoJob:
    """The same ``state["segments"]``-dict-to-list assembly ``core/graph/nodes/finalize.py
    ::finalize`` does at the very end, applied mid-run: ``state["job"].segments`` is only ever
    populated by ``finalize`` itself, so a snapshot taken before then always carries an empty
    list there even though ``state["segments"]`` (the fan-out accumulator
    ``core/graph/state.py::merge_segments`` merges concurrent writes into) already has real data.
    ``plan_segments`` seeds every index up front, unfilled, so this is already the full-length
    list by the very first "end" event -- later per-segment nodes fill individual entries in as
    they converge on each index, rather than new cards appearing one at a time.
    """
    job = values["job"]
    segments = values.get("segments") or {}
    if not segments:
        return job
    ordered = [segments[i] for i in sorted(segments)]
    return job.model_copy(update={"segments": ordered})
