"""Closes the run out: the ``segments`` dict the fan-out built, folded back onto the job."""

from core.graph.state import GraphState
from core.models import JobStatus


async def finalize(state: GraphState) -> dict:
    """Copy ``segments`` onto ``job`` in index order and mark it ``SUCCEEDED``.

    Runs only once every fan-out task has converged on this node, so ``segments`` is complete by
    construction -- there is nothing here to check for.
    """
    job = state["job"]
    ordered = [state["segments"][i] for i in sorted(state["segments"])]
    updated_job = job.model_copy(update={"segments": ordered, "status": JobStatus.SUCCEEDED})
    return {"job": updated_job}
