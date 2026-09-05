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

from adapters.local import hyperframes_check, hyperframes_cli
from adapters.local.playwright_capture import PlaywrightCapture
from interfaces import RenderBackend, RenderFailed

MAX_BACKOFF_S = 10.0

# T18A: a flat 60s timeout, previously shared by captures and full renders, was measured against a
# 3-second/90-frame sample (D16) and is contradicted by this project's own successful longer
# renders -- ~600-frame (25s) segments completed inside it, implying throughput D16 understated by
# at least 4x. Renders now scale with content instead of guessing a constant; captures (single
# frames, always cheap) keep the flat `timeout_s`.
RENDER_TIMEOUT_FLOOR_S = 180.0
RENDER_TIMEOUT_FACTOR = 12.0

# T18J: the real geometry of _captions.html's caption band, as canvas fractions
# (926/1080=0.8574 top, 1016/1080=0.9407 bottom) -- confirmed empirically
# (tests/test_render_segment_live.py's own Phase-0 spike, D116) that a caption_zone_collision
# finding folds into the SAME "layout" category validate_geometry already reads, under no
# separate top-level JSON key, so passing this is the whole fix; no new parsing needed. Also
# confirmed to add no measurable cost (~15-18s either way against a real composition) -- it is a
# geometric check against samples the tool already takes, not a new sampling pass.
CAPTION_ZONE = "x0=0;y0=0.8574;x1=1;y1=0.9407;severity=error"


def render_timeout_s(duration_ms: int) -> float:
    """The render timeout for a segment of ``duration_ms``: generous, and never below the floor."""
    return max(RENDER_TIMEOUT_FLOOR_S, duration_ms / 1000 * RENDER_TIMEOUT_FACTOR)


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
        workers: int | str = "auto",
    ) -> None:
        if max_concurrency < 1:
            raise ValueError(f"max_concurrency must be at least 1, got {max_concurrency}")
        if max_attempts < 1:
            raise ValueError(f"max_attempts must be at least 1, got {max_attempts}")

        self.quality = quality
        self.timeout_s = timeout_s
        self.max_attempts = max_attempts
        self.workers = workers
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
        # the second source of truth D20 already rejected for width/height. It is used here only
        # to scale this call's own timeout (T18A) -- a longer segment legitimately needs longer.
        retryer = self._retryer()
        async with self._semaphore:
            return await retryer(
                hyperframes_cli.render,
                composition,
                dest,
                fps=fps,
                quality=self.quality,
                timeout_s=render_timeout_s(duration_ms),
                workers=self.workers,
            )

    async def lint(self, composition: Path) -> list[str]:
        # No retry, no semaphore: lint never raises by contract, and it is the fast static check
        # meant to run before the expensive path, not compete with it for concurrency slots.
        return await hyperframes_cli.lint(composition, timeout_s=self.timeout_s)

    async def check(
        self, project_dir: Path, *, caption_zone: str | None = None, contrast: bool = True
    ) -> dict:
        """T18A's second, richer gate (motion, layout, WCAG contrast) -- not on the
        ``RenderBackend`` ABC (see ``hyperframes_check.py``'s docstring for why). No retry: like
        ``lint``, it is diagnostic and its own non-determinism (D96) must not be masked by a retry
        that just happens to land on the passing run.
        """
        return await hyperframes_check.check(
            project_dir, caption_zone=caption_zone, contrast=contrast
        )

    async def validate_geometry(self, composition: Path) -> list[str]:
        # T18H: at_transitions/frame_check both measured off by default here -- a real, dense
        # segment (t18g-showcase-git's own segment 2, 1025 lines) costs ~15s at samples=9 with
        # both off, ~56s with --at-transitions added, for the SAME errorCount on that composition
        # (a sustained crowding bug, not a brief transition-seam one). Every real-render bug this
        # project has found so far has been sustained across many samples, not a one-frame
        # transition artifact, so the ~4x cost was not buying anything on the one case measured --
        # a decision to record at checkpoint, not a guess (D16/D99's own lesson about unmeasured
        # constants). contrast is a separate concern (already covered by the local_live sweep) and
        # materially slower still, so it stays off here regardless.
        #
        # The semaphore below shares this class's own concurrency budget with capture()/render()
        # (the class docstring's own rule) -- `check` spawns its own headless-browser process tree
        # the same way `render` does, and this method (unlike the diagnostic `check()` above) is
        # wired into every real segment's render path, so leaving it unbounded would let it starve
        # the very renders it gates (found by review, before this ever ran against a real job).
        #
        # T18J: caption_zone added, measured to cost nothing extra (~15-18s either way against a
        # real composition -- it is a geometric check against samples already taken, not a new
        # sampling pass, see CAPTION_ZONE's own comment). at_transitions/frame_check stay off:
        # at_transitions was re-measured this session against the two real overlaps a user
        # flagged and changed nothing about their classification (occurrences 3->7, severity
        # unchanged) -- the actual fix for those was is_fatal_geometry_finding, not more sampling.
        async with self._semaphore:
            payload = await hyperframes_check.check(
                composition.parent,
                at_transitions=False,
                frame_check=False,
                contrast=False,
                caption_zone=CAPTION_ZONE,
            )
        # `layout.findings` alone is not enough: if the browser check itself never ran to
        # completion (a page crash, a JS exception mid-composition, a navigation timeout), the CLI
        # does not raise or change the JSON's shape -- it records the failure as a `runtime`
        # finding and still returns `layout: {findings: [], ...}`, indistinguishable from a
        # composition that genuinely has no geometry problems. `lint()` (hyperframes_cli.py) has
        # its own equivalent guard for exactly this "the tool didn't run" vs. "the tool found
        # nothing" distinction; this folds `runtime` findings in for the same reason (found by
        # review) rather than trusting an empty `layout.findings` on its own.
        #
        # T18J: `motion` findings folded in too -- this call already pays for computing them
        # (no new flag, no new cost), and they were previously silently dropped on the floor.
        return [
            f"[{finding.get('severity', 'error')}] {finding.get('code', 'unknown')}: "
            f"{finding.get('message', '')}"
            for section in (
                payload.get("runtime", {}),
                payload.get("layout", {}),
                payload.get("motion", {}),
            )
            for finding in section.get("findings", [])
        ]

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
