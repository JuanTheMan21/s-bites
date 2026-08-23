"""Turning a Playwright or HyperFrames-CLI failure into ``RenderFailed``.

Shared by ``playwright_capture.py`` and ``hyperframes_cli.py`` so the two capture paths --
one driving a browser directly, one shelling to a Node CLI -- report failure through the same
door. ``capture`` and ``render`` are the only two contract methods that raise here; ``lint``
never raises by contract and has no translation to do.
"""

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from interfaces import RenderFailed


def translate(exc: Exception, *, context: str) -> RenderFailed:
    """Return the ``RenderFailed`` that carries ``exc``'s meaning across the boundary.

    Never raises and never returns ``None`` -- callers do ``raise translate(exc, ...) from exc``.
    ``context`` names what was being attempted (e.g. a composition path) so the message is
    useful without the caller having to reconstruct it from the exception alone.
    """
    if isinstance(exc, PlaywrightTimeoutError):
        return RenderFailed(f"{context}: page did not become ready in time: {exc}")
    if isinstance(exc, PlaywrightError):
        return RenderFailed(f"{context}: browser automation failed: {exc}")
    if isinstance(exc, FileNotFoundError):
        return RenderFailed(f"{context}: could not find the command to run ({exc})")
    if isinstance(exc, TimeoutError):
        return RenderFailed(f"{context}: timed out: {exc}")
    return RenderFailed(f"{context}: {exc.__class__.__name__}: {exc}")
