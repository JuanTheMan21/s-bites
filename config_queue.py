"""``JobQueue`` resolution, split out of ``config.py`` the same way ``config_render.py`` split out
``RenderBackend`` resolution (T18A) -- to stay under the 200-line ceiling and to keep this one
seam's growth (a second stub-until-a-future-task bridge) in its own file rather than crowding the
module every other interface's resolution lives in.

Still config-seam code, not adapter logic: it names the same two concrete classes ``config.py``
already imported (``LocalJobQueue``, ``ServiceBusJobQueue``) and nothing else does.
``config.py`` still owns calling this and every other interface's resolution; this module has no
other caller and no other reason to exist.
"""

from collections.abc import Mapping

from adapters.azure.job_queue import ServiceBusJobQueue
from adapters.local.job_queue import LocalJobQueue
from interfaces import JobQueue


def queue_env(env: Mapping[str, str]) -> str:
    """``QUEUE_ENV`` is the same bridge ``config_render.py::render_env`` already is for
    ``RenderBackend``: ``ServiceBusJobQueue`` is still T34's stub (every method raises
    ``NotImplementedError``), so ``RUNTIME_ENV=azure`` alone cannot complete a single job through
    the API -- ``POST /jobs`` 500s the instant ``JobRunner`` tries to enqueue it. Defaults to
    ``RUNTIME_ENV`` when unset, so nothing changes for a caller that has never heard of it; setting
    ``QUEUE_ENV=local`` under ``RUNTIME_ENV=azure`` pairs the real in-process ``LocalJobQueue``
    with real Azure LLM/TTS/Storage -- the same "real everything else, local for the one stub"
    shape ``RENDER_ENV`` already established, and what lets ``uvicorn api.main:app`` actually run
    a job the way ``cli.py`` (which never touches ``JobQueue`` at all) already could. Not a second
    permanent stack switch: T34 closes this by making ``QUEUE_ENV`` unnecessary, not by teaching
    it a third value.
    """
    value = env.get("QUEUE_ENV", "").strip()
    return value or env.get("RUNTIME_ENV", "")


def resolve(env: Mapping[str, str]) -> JobQueue:
    """Resolve the job queue against ``queue_env(env)``, not ``RUNTIME_ENV`` directly."""
    if queue_env(env) == "local":
        return LocalJobQueue()
    # Stub until T34 (D25) -- an empty connection string is honest, since it is never dialed.
    return ServiceBusJobQueue(
        env.get("AZURE_SERVICE_BUS_CONNECTION_STRING", ""),
        env.get("AZURE_SERVICE_BUS_QUEUE", "").strip() or "video-jobs",
    )
