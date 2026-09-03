"""Runs the real FastAPI app against ``tests/fakes/*`` under uvicorn -- no Azure spend, no live
credentials, a whole job completes through real ffmpeg in seconds. This is the frontend build
loop: point ``web/.env``'s ``VITE_API_BASE`` at this instead of a real ``RUNTIME_ENV=azure``
backend and every page -- submission, live stages, tier badges, player, resume, downloads -- is
exercisable end to end, repeatedly, for free.

``FAKE_STAGE_DELAY_MS`` (optional): a completed job flashes past in under a second against fakes,
too fast to watch the stage timeline actually animate. Set it to slow the fake TTS/render calls
down to human speed without touching ``tests/fakes/*`` itself.
"""

import asyncio
import dataclasses
import os
import re

import uvicorn

from api.app import create_app
from tests.api_fixtures import FPS, FRAME_BUDGET, fake_adapters
from tests.graph_pipeline_fixtures import PhaseQueueLLMProvider, seeded_llm

DEFAULT_PORT = 8000

# core/graph/nodes/outline.py's own prompt states the exact count it needs: "Produce exactly N
# segments." -- read back here rather than guessed.
SEGMENT_COUNT_RE = re.compile(r"[Pp]roduce exactly (\d+) segments")


class DynamicSegmentLLMProvider(PhaseQueueLLMProvider):
    """``tests/graph_pipeline_fixtures.py::seeded_llm(segment_count)`` assumes one known count,
    fixed at construction -- correct for a test that submits exactly one job, wrong for this
    process, which serves whichever duration a real user picks from T25's duration chips
    (3/7/10 min -> 6/15/21 segments, none of which match the test suite's own 4-segment
    default). Refilling from the outline prompt's stated count, right before the first call of
    each new job, makes every duration option actually work rather than only the one the test
    fixtures happened to be tuned for.

    Caveat (project-reviewer, T24-T28 checkpoint): the refill guard only checks that the queue is
    *empty*, not which job it belongs to. A clean run always drains its queue exactly (confirmed:
    ``seeded_llm(N)``'s exact call sequence is fully consumed by a successful run), so this is
    safe for this script's actual dev-loop use. It is **not** safe across an *injected* failure
    (``fail_next``) that leaves a job's queue partway consumed -- a differently-sized job
    submitted next could silently draw from those mismatched leftovers instead of getting a fresh
    refill. Fine for manual UI exploration (this script's only purpose); do not reuse this class
    anywhere failure-injection and dynamic sizing need to coexist correctly.
    """

    async def generate(self, prompt, schema, *, system=None):
        if not self.responses:
            match = SEGMENT_COUNT_RE.search(prompt)
            if match:
                self.responses = seeded_llm(int(match.group(1))).responses
        return await super().generate(prompt, schema, system=system)


def _slow_down(adapters, delay_ms: int) -> None:
    """Wraps the fake TTS/render calls in a sleep, in place, on this one bundle."""
    for target, method in ((adapters.tts, "synthesize"), (adapters.render, "render")):
        original = getattr(target, method)

        async def delayed(*args, _original=original, **kwargs):
            await asyncio.sleep(delay_ms / 1000)
            return await _original(*args, **kwargs)

        setattr(target, method, delayed)


def main() -> None:
    adapters = dataclasses.replace(fake_adapters(), llm=DynamicSegmentLLMProvider())
    delay_ms = int(os.environ.get("FAKE_STAGE_DELAY_MS", "0"))
    if delay_ms > 0:
        _slow_down(adapters, delay_ms)

    app = create_app(adapters, frame_budget=FRAME_BUDGET, fps=FPS)
    uvicorn.run(app, host="127.0.0.1", port=DEFAULT_PORT)


if __name__ == "__main__":
    main()
