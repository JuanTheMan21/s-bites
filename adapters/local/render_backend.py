"""``RenderBackend``: Playwright drives stills, the HyperFrames CLI drives full renders and lint.

Two capture paths, one contract. ``capture`` (Tier 0/1) opens a composition in a browser this
class keeps alive across calls and seeks it (``playwright_capture.py``) -- see that module for why
Playwright rather than the CLI's own ``snapshot``. ``render`` (Tier 2) and ``lint`` shell to
``npx hyperframes`` (``hyperframes_cli.py``), which is what CLAUDE.md already names as the render
adapter's job for those two verbs.

Retry follows the same shape as the Azure adapters: a fresh ``tenacity.AsyncRetrying`` per call,
``reraise=True``, bounded by ``max_attempts``. ``RenderFailed``'s own docstring says why retrying
is worth it here -- browser crashes and timeouts do not reproduce reliably -- and why ``lint``
gets none: it never raises in the first place.
"""

import asyncio
from collections.abc import Sequence
from pathlib import Path

from tenacity import AsyncRetrying, RetryCallState, stop_after_attempt, wait_exponential_jitter

from adapters.local import hyperframes_cli
from adapters.local.playwright_capture import PlaywrightCapture
from interfaces import RenderBackend, RenderFailed

MAX_BACKOFF_S = 10.0


class PlaywrightHyperFramesRenderBackend(RenderBackend):
    """Constructor arguments are explicit, never read from ``os.environ`` -- same reasoning as
    the Azure adapters (D51): ``config.py`` is the only module that may know which one is active.

    ``max_concurrency`` bounds concurrent browser pages and concurrent ``hyperframes`` subprocess
    invocations alike, sharing one semaphore -- both are expensive per-unit work on the same
    machine, and letting one type starve the other under load is not a distinction worth making.
    """

    def __init__(
        self,
        *,
        max_concurrency: int = 4,
        max_attempts: int = 2,
        quality: str = "standard",
        timeout_s: float = 60.0,
    ) -> None:
        if max_concurrency < 1:
            raise ValueError(f"max_concurrency must be at least 1, got {max_concurrency}")
        if max_attempts < 1:
            raise ValueError(f"max_attempts must be at least 1, got {max_attempts}")

        self.quality = quality
        self.timeout_s = timeout_s
        self.max_attempts = max_attempts
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._capture_engine = PlaywrightCapture(browser_timeout_s=timeout_s)

    async def capture(
        self, composition: Path, dest_dir: Path, *, at_seconds: Sequence[float]
    ) -> list[Path]:
        retryer = self._retryer()
        async with self._semaphore:
            return await retryer(
                self._capture_engine.capture, composition, dest_dir, at_seconds=at_seconds
            )

    async def render(self, composition: Path, dest: Path, *, fps: int, duration_ms: int) -> Path:
        # duration_ms is not passed to the CLI: the composition's own data-duration attribute
        # governs render length (it was written from the same measured duration by whoever
        # authored the composition, per Invariant 1), and passing it again here would be exactly
        # the second source of truth D20 already rejected for width/height.
        retryer = self._retryer()
        async with self._semaphore:
            return await retryer(
                hyperframes_cli.render,
                composition,
                dest,
                fps=fps,
                quality=self.quality,
                timeout_s=self.timeout_s,
            )

    async def lint(self, composition: Path) -> list[str]:
        # No retry, no semaphore: lint never raises by contract, and it is the fast static check
        # meant to run before the expensive path, not compete with it for concurrency slots.
        return await hyperframes_cli.lint(composition, timeout_s=self.timeout_s)

    def _retryer(self) -> AsyncRetrying:
        return AsyncRetrying(
            stop=stop_after_attempt(self.max_attempts),
            wait=wait_exponential_jitter(initial=1.0, max=MAX_BACKOFF_S),
            retry=_is_retryable,
            reraise=True,
        )

    async def aclose(self) -> None:
        """Release the browser this instance kept alive across calls.

        Not on the ``RenderBackend`` contract -- same reasoning as the Azure adapters' ``aclose``
        (D55): the fake has nothing to close, and the owner (``config.py`` at T13, the FastAPI
        lifespan at T19) calls this.
        """
        await self._capture_engine.aclose()


def _is_retryable(state: RetryCallState) -> bool:
    exc = state.outcome.exception() if state.outcome else None
    return isinstance(exc, RenderFailed)
