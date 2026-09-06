"""``JobQueue`` resolution, split out of ``config.py`` the same way ``config_render.py`` split out
``RenderBackend`` resolution (T18A) -- to stay under the 200-line ceiling and to keep this seam's
own bridge in its own file rather than crowding the module every other interface's resolution
lives in.

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
    """``QUEUE_ENV`` is the same bridge shape ``config_render.py::render_env`` already is for
    ``RenderBackend``. **T34 made ``ServiceBusJobQueue`` real** -- it is no longer a stub, and
    ``RUNTIME_ENV=azure`` alone now completes a job through the API. This bridge stays useful
    regardless: pairing the real in-process ``LocalJobQueue`` with real Azure LLM/TTS/Storage
    (``QUEUE_ENV=local`` under ``RUNTIME_ENV=azure``) is a genuinely faster local dev loop -- no
    namespace round trip per enqueue/dequeue -- not a workaround for anything missing. Defaults to
    ``RUNTIME_ENV`` when unset, so nothing changes for a caller that has never heard of it.
    """
    value = env.get("QUEUE_ENV", "").strip()
    return value or env.get("RUNTIME_ENV", "")


def resolve(env: Mapping[str, str]) -> JobQueue:
    """Resolve the job queue against ``queue_env(env)``, not ``RUNTIME_ENV`` directly."""
    if queue_env(env) == "local":
        return LocalJobQueue()
    return ServiceBusJobQueue(
        env.get("AZURE_SERVICE_BUS_CONNECTION_STRING", ""),
        env.get("AZURE_SERVICE_BUS_QUEUE", "").strip() or "video-jobs",
    )
