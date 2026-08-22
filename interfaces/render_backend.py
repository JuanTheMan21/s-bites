"""The contract for turning a composition into pixels."""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from pathlib import Path


class RenderBackend(ABC):
    """Screenshots or renders a composition -- an HTML file -- to images or video.

    Three primitives rather than one method per render tier. The tier system is a budgeting
    decision that belongs to ``core/tier_resolver.py`` and the modules in ``rendering/``;
    baking it into this contract would mean adding a tier later changes the interface and
    every implementation of it. So Tier 0 and Tier 1 both call ``capture`` -- one timestamp
    or several -- and Tier 2 calls ``render``.

    Frame dimensions are absent by design: the composition root carries ``data-width`` and
    ``data-height``, and passing them again here creates a second source of truth that can
    disagree with the file being rendered.
    """

    @abstractmethod
    async def capture(
        self, composition: Path, dest_dir: Path, *, at_seconds: Sequence[float]
    ) -> list[Path]:
        """Screenshot ``composition`` at each timeline position in ``at_seconds``.

        Returns one image path per requested position, **in the order requested**, written
        under ``dest_dir`` (created if absent). Seeking the timeline rather than waiting on
        wall-clock time is what makes a single still and a multi-state reveal the same
        operation with a different number of timestamps.

        Raises:
            RenderFailed: the page could not be loaded or captured.
        """

    @abstractmethod
    async def render(self, composition: Path, dest: Path, *, fps: int, duration_ms: int) -> Path:
        """Render ``composition`` frame by frame to a video at ``dest``. Returns ``dest``.

        ``duration_ms`` is **milliseconds** and comes from measured narration audio, so the
        clip matches its narration exactly. Frame count is ``duration_ms / 1000 * fps``, and
        it is the only meaningful cost lever -- resolution measurably is not.

        Raises:
            RenderFailed: the renderer ran and produced no usable output.
        """

    @abstractmethod
    async def lint(self, composition: Path) -> list[str]:
        """Validate ``composition`` without rendering it. Returns findings, newest concern
        first; an **empty list means valid**.

        Never raises on an invalid composition -- an invalid file is the expected input to
        this method, and returning findings lets the caller log them all rather than
        discovering them one exception at a time. Deciding a finding is fatal is the
        caller's job, and ``CompositionInvalid`` is the caller's exception to raise.

        Catching a bad composition here costs a second; catching it mid-render costs minutes
        of a job that is already running.
        """
