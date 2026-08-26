"""``RenderBackend`` resolution, split out of ``config.py`` (T18A) to keep it under the 200-line
ceiling once the ``RENDER_ENV`` bridge (D92's real fix) and worker/quality wiring landed.

This is still config-seam code, not adapter logic: it names the same two concrete classes
``config.py`` already imported (``PlaywrightHyperFramesRenderBackend``,
``ContainerAppsRenderBackend``) and nothing else does. CLAUDE.md's "config.py is the only module
naming concrete adapter classes" is about there being **one seam** where that happens, not a single
physical file -- ``config.py`` still owns calling this, still owns every other interface's
resolution, and this module has no other caller and no other reason to exist.
"""

from collections.abc import Mapping

from adapters.azure.render_backend import ContainerAppsRenderBackend
from adapters.local.render_backend import PlaywrightHyperFramesRenderBackend
from interfaces import RenderBackend


def render_env(env: Mapping[str, str]) -> str:
    """T18A: ``RENDER_ENV`` is the explicit, temporary bridge D92 flagged as needed until T35 --
    ``ContainerAppsRenderBackend`` is still a stub, so ``RUNTIME_ENV=azure`` alone cannot drive a
    render. Defaults to ``RUNTIME_ENV`` when unset, so nothing changes for a caller that has never
    heard of it; setting ``RENDER_ENV=local`` under ``RUNTIME_ENV=azure`` is what lets ``cli.py``
    run a full job standalone -- real Azure LLM/TTS/Storage paired with the real local render
    backend -- without hand-mixing adapters outside of labeled code. Not a second permanent stack
    switch: T35 closes this by making ``RENDER_ENV`` unnecessary, not by teaching it a third value.
    """
    value = env.get("RENDER_ENV", "").strip()
    return value or env.get("RUNTIME_ENV", "")


def resolve(env: Mapping[str, str]) -> RenderBackend:
    """Resolve the render backend against ``render_env(env)``, not ``RUNTIME_ENV`` directly."""
    if render_env(env) == "local":
        workers_raw = env.get("RENDER_WORKERS", "auto").strip() or "auto"
        workers: int | str = int(workers_raw) if workers_raw.isdigit() else workers_raw
        max_concurrency_raw = env.get("RENDER_MAX_CONCURRENCY", "4").strip() or "4"
        try:
            max_concurrency = int(max_concurrency_raw)
        except ValueError as exc:
            raise RuntimeError(
                f"RENDER_MAX_CONCURRENCY must be an integer, got {max_concurrency_raw!r}"
            ) from exc
        return PlaywrightHyperFramesRenderBackend(
            max_concurrency=max_concurrency,
            quality=env.get("RENDER_QUALITY", "standard").strip() or "standard",
            workers=workers,
        )
    # Stub until T35 (D25) -- neither value is dialed before then.
    resource_group = env.get("AZURE_RESOURCE_GROUP", "")
    container_apps_env = env.get("AZURE_CONTAINER_APPS_ENVIRONMENT", "")
    return ContainerAppsRenderBackend(resource_group, container_apps_env)
