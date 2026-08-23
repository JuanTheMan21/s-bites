"""Screenshotting a composition at explicit timeline positions, via Playwright directly.

Tier 0/1 need a handful of stills per segment, and the HyperFrames CLI has no verb that fits
``capture``'s ``Sequence[float] -> list[Path]`` contract cheaply -- the closest, ``snapshot``,
boots a fresh Node process and browser per invocation. Driving one already-open browser page
instead is the direct implementation of "shortest time to video": the browser is launched once
(lazily, on first use) and kept alive across calls, not rebuilt per capture.

The seek mechanism is D15's, verified during the T4 toolchain spike: a **paused GSAP timeline**
registered as ``window.__timelines["<composition-id>"]``. ``seek(t, true)`` moves it to ``t``
seconds without firing entrance/exit callbacks, so a screenshot at that instant matches what the
CLI's own frame-by-frame renderer would have produced there.
"""

import asyncio
from collections.abc import Sequence
from pathlib import Path

from playwright.async_api import Browser, Playwright, async_playwright

from adapters.local.render_errors import translate
from interfaces import RenderFailed

_READY = "() => window.__timelines && Object.keys(window.__timelines).length > 0"
_COMPOSITION_ID = "el => el.dataset.compositionId"
# Braces, not an implicit-return arrow: GSAP's .seek() returns the timeline itself for chaining,
# and Playwright then has to serialise that back to Python -- a large, circular object graph that
# hangs the round trip rather than erroring. Discarding the return value is the whole fix.
_SEEK = "([id, t]) => { window.__timelines[id].seek(t, true); }"


class PlaywrightCapture:
    """Owns one lazily-launched Chromium instance, reused across every ``capture`` call."""

    def __init__(self, *, browser_timeout_s: float) -> None:
        self._browser_timeout_ms = browser_timeout_s * 1000
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._launch_lock = asyncio.Lock()

    async def capture(
        self, composition: Path, dest_dir: Path, *, at_seconds: Sequence[float]
    ) -> list[Path]:
        dest_dir.mkdir(parents=True, exist_ok=True)
        browser = await self._ensure_browser()
        context = f"capture {composition}"

        page = None
        try:
            # Inside the try, not before it: a crashed browser most often fails right here (the
            # first call that has to reach it over CDP), not at goto -- and this method's whole
            # contract is that a browser failure comes back as RenderFailed, retryable.
            page = await browser.new_page()
            await page.goto(composition.resolve().as_uri(), timeout=self._browser_timeout_ms)
            await page.wait_for_function(_READY, timeout=self._browser_timeout_ms)
            comp_id = await page.eval_on_selector("[data-composition-id]", _COMPOSITION_ID)
            if comp_id is None:
                raise RenderFailed(f"{context}: no element carries data-composition-id")
            await _set_viewport_from_composition(page)

            paths: list[Path] = []
            for n, t in enumerate(at_seconds):
                await page.evaluate(_SEEK, [comp_id, t])
                path = dest_dir / f"{composition.stem}-{n:03d}.png"
                await page.screenshot(path=str(path))
                paths.append(path)
            return paths
        except RenderFailed:
            raise
        except Exception as exc:
            raise translate(exc, context=context) from exc
        finally:
            if page is not None:
                await page.close()

    async def _ensure_browser(self) -> Browser:
        if self._browser is not None:
            return self._browser
        async with self._launch_lock:
            if self._browser is None:  # re-check: another task may have launched it while waiting
                try:
                    self._playwright = await async_playwright().start()
                    self._browser = await self._playwright.chromium.launch()
                except Exception as exc:
                    # A launch failure must not leave a started driver behind for the next call
                    # to silently overwrite and leak -- reset to a clean slate before translating.
                    if self._playwright is not None:
                        await self._playwright.stop()
                        self._playwright = None
                    raise translate(exc, context="launching the browser") from exc
            return self._browser

    async def aclose(self) -> None:
        """Release the browser and its driver process. Not on the ``RenderBackend`` contract --
        see ``adapters/local/render_backend.py``'s ``aclose`` for why."""
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None


async def _set_viewport_from_composition(page) -> None:
    """Read ``data-width``/``data-height`` off the root rather than passing our own (D20): a
    second source of truth for the frame size can disagree with the file being rendered."""
    width = await page.eval_on_selector("[data-composition-id]", "el => Number(el.dataset.width)")
    height = await page.eval_on_selector("[data-composition-id]", "el => Number(el.dataset.height)")
    await page.set_viewport_size({"width": width, "height": height})
