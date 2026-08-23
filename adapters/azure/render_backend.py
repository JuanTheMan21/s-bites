"""``RenderBackend`` stub backed by Container Apps. Real implementation lands at T35 (D25).

Matches ``interfaces.RenderBackend`` exactly and raises ``NotImplementedError`` naming what is
missing -- see ``adapters/azure/job_queue.py``'s module docstring for why a signature-matched stub
is the point, not a shortcut.
"""

from collections.abc import Sequence
from pathlib import Path

from interfaces import RenderBackend


class ContainerAppsRenderBackend(RenderBackend):
    """Constructor shape is provisional -- T35 finalises it against the real Container Apps job
    it dispatches to, and against the image built there (Playwright's Chromium *and*
    HyperFrames' Chrome Headless Shell, per D15, plus vendored GSAP)."""

    def __init__(self, resource_group: str, environment_name: str) -> None:
        self.resource_group = resource_group
        self.environment_name = environment_name

    async def capture(
        self, composition: Path, dest_dir: Path, *, at_seconds: Sequence[float]
    ) -> list[Path]:
        raise NotImplementedError(
            "ContainerAppsRenderBackend.capture: real Container Apps capture lands at T35 (D25)"
        )

    async def render(self, composition: Path, dest: Path, *, fps: int, duration_ms: int) -> Path:
        raise NotImplementedError(
            "ContainerAppsRenderBackend.render: real Container Apps render lands at T35 (D25)"
        )

    async def lint(self, composition: Path) -> list[str]:
        raise NotImplementedError(
            "ContainerAppsRenderBackend.lint: real Container Apps lint lands at T35 (D25)"
        )
