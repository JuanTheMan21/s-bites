"""``python worker.py`` -- the standalone worker process (T34), the third edge in this repo
alongside ``cli.py`` and ``api/main.py``: reads ``RUNTIME_ENV``/``FRAME_BUDGET``/``FPS`` from the
process environment and runs ``api.runner.JobRunner``'s same loop with nothing else attached.

Splits the worker out of the API process so a container running this can scale independently of
one serving requests (T35). ``api/app.py``'s in-process worker (``run_worker=True``, its default)
still exists and still works standalone -- this is an additional way to run the same
``JobRunner``, not a replacement for the API's own.

**Deliberately never calls ``adapters.events.start()``.** This process only ever publishes
(``JobRunner`` calling ``publish``/``end_stream``); it never subscribes. ``config_events.py``
already documents ``ServiceBusEventChannel`` as managing exactly one fixed subscription -- if this
process also started its own receive pump against that same subscription, Service Bus would split
delivery between it and the API's real subscriber, and roughly half of every job's progress events
would land in this process's own ``_local`` channel, which nothing here ever reads, and vanish
silently. Only ``api/app.py``'s lifespan calls ``start()``, because the API is the one place an
SSE subscriber can ever actually be.

Graceful shutdown matters here in a way it didn't when the worker shared the API's lifespan:
Container Apps stops a replica with SIGTERM, and a runner that does not hear it keeps rendering
until the platform kills it outright, abandoning whatever job was mid-flight with no chance to let
the queue's own lease expiry (rather than a hard kill) return it cleanly. ``asyncio.
add_signal_handler`` is the correct way to hook that, but the Windows ``ProactorEventLoop`` does
not implement it -- caught explicitly and falls back to ``signal.signal``, since this worker also
has to actually start on the developer's own Windows machine, not just in a Linux container.
"""

import asyncio
import logging
import os
import signal

from dotenv import load_dotenv

from api.job_store import JobStore
from api.runner import JobRunner
from config import build_adapters, close_adapters

logger = logging.getLogger(__name__)


def _required_int(name: str) -> int:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is not set. Copy .env.example to .env and fill it in.")
    try:
        return int(value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer, got {value!r}") from exc


def _install_shutdown_handler(stop_event: asyncio.Event) -> None:
    loop = asyncio.get_running_loop()
    try:
        loop.add_signal_handler(signal.SIGTERM, stop_event.set)
        loop.add_signal_handler(signal.SIGINT, stop_event.set)
    except NotImplementedError:
        # Windows' ProactorEventLoop (the default, and required elsewhere in this project for
        # subprocess support -- see api/main.py's own docstring) does not support
        # add_signal_handler. signal.signal still works: Python delivers the signal on the main
        # thread between bytecode instructions and asyncio's own wakeup mechanism picks up the
        # event-loop-safe .set() call from there.
        signal.signal(signal.SIGTERM, lambda *_: stop_event.set())
        signal.signal(signal.SIGINT, lambda *_: stop_event.set())


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    load_dotenv()

    adapters = build_adapters()
    store = JobStore(adapters.storage)
    runner = JobRunner(
        adapters,
        store,
        adapters.events,
        frame_budget=_required_int("FRAME_BUDGET"),
        fps=_required_int("FPS"),
    )

    stop_event = asyncio.Event()
    _install_shutdown_handler(stop_event)

    runner.start()
    logger.info("worker started, waiting for jobs")
    try:
        await stop_event.wait()
        logger.info("shutdown requested, stopping worker")
    finally:
        await runner.stop()
        await close_adapters(adapters)


if __name__ == "__main__":
    asyncio.run(main())
