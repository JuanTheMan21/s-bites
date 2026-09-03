"""``RenderBackend``, writing placeholder files instead of driving a browser."""

import base64
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from interfaces import RenderBackend
from tests.fakes.failure_injection import FailureInjector

# A real 1x1 PNG. Captures are genuine image files rather than empty stubs, so a caller that
# checks a screenshot decodes -- or hands one to ffmpeg at T18 -- is testing something.
PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)

# There is no equivalent for video: a valid MP4 needs ffmpeg, and an offline fake that shells
# out to a binary is not offline. The marker text is for whoever opens the file wondering why
# it will not play. T18's mux work must run against the real local adapter, not this.
NOT_AN_MP4 = b"FakeRenderBackend placeholder -- not a real MP4.\n"


@dataclass(frozen=True, slots=True)
class CaptureCall:
    composition: Path
    at_seconds: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class RenderCall:
    composition: Path
    fps: int
    duration_ms: int


class FakeRenderBackend(FailureInjector, RenderBackend):
    """Records what it was asked to render and writes something plausible at the destination.

    ``lint`` returns findings and never raises, even for a composition that is nonsense -- an
    invalid file is this method's expected input. Deciding a finding is fatal belongs to the
    caller, and ``CompositionInvalid`` is the caller's exception to raise (D23), so no fake
    raises it.
    """

    def __init__(
        self,
        findings: Sequence[str] = (),
        geometry_findings: Sequence[str] = (),
        geometry_findings_sequence: Sequence[Sequence[str]] | None = None,
    ) -> None:
        self.findings = list(findings)
        self.geometry_findings = list(geometry_findings)
        # T18I: geometry_findings_sequence lets a test simulate render_scene.py's own recovery
        # sequence (first attempt fails, a re-authored/fallback attempt succeeds) -- one entry
        # per validate_geometry call, in order; the LAST entry repeats once exhausted, so a test
        # doesn't have to predict exactly how many attempts a given scenario takes. None (the
        # default) keeps the old single-static-list behaviour every existing caller relies on.
        self._geometry_findings_sequence = (
            [list(entry) for entry in geometry_findings_sequence]
            if geometry_findings_sequence is not None
            else None
        )
        self.validate_geometry_calls = 0
        self.captures: list[CaptureCall] = []
        self.renders: list[RenderCall] = []

    async def capture(
        self, composition: Path, dest_dir: Path, *, at_seconds: Sequence[float]
    ) -> list[Path]:
        self._maybe_fail("capture")
        self.captures.append(CaptureCall(composition, tuple(at_seconds)))
        dest_dir.mkdir(parents=True, exist_ok=True)

        # Named by position, not by timestamp: the same second may legitimately be requested
        # twice, and the contract promises one image per request in the order requested.
        paths = [dest_dir / f"{composition.stem}-{n:03d}.png" for n in range(len(at_seconds))]
        for path in paths:
            path.write_bytes(PNG_1X1)
        return paths

    async def render(self, composition: Path, dest: Path, *, fps: int, duration_ms: int) -> Path:
        self._maybe_fail("render")
        self.renders.append(RenderCall(composition, fps, duration_ms))
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(NOT_AN_MP4)
        return dest

    async def lint(self, composition: Path) -> list[str]:
        self._maybe_fail("lint")
        return list(self.findings)

    async def validate_geometry(self, composition: Path) -> list[str]:
        self._maybe_fail("validate_geometry")
        if self._geometry_findings_sequence is not None:
            index = min(self.validate_geometry_calls, len(self._geometry_findings_sequence) - 1)
            self.validate_geometry_calls += 1
            return list(self._geometry_findings_sequence[index])
        self.validate_geometry_calls += 1
        return list(self.geometry_findings)
