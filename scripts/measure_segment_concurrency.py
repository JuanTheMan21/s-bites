"""D47's third carry-forward, closed with a number: does DiskStorage's synchronous I/O stall
concurrent jobs sharing one event loop, now that T14's per-segment fan-out actually generates
concurrency to measure it with?

Run by hand -- ``python -m scripts.measure_segment_concurrency`` from the repo root -- against
the real local ``DiskStorage`` (never imported from core/graph/ itself; scripts/ sits outside the
boundary, same precedent as scripts/verify_azure.py, D51). TTS stays fake: this measures disk
contention, not network latency, and a real TTS call would drown the signal in synthesis time.

``DiskSkillRegistry`` is not separately exercised here -- no node in this skeleton calls
``SkillRegistry`` yet -- but its reads share `DiskStorage`'s exact shape (synchronous I/O inside
an ``async def``, per D47), so this measurement's answer applies to both rather than needing a
second, contrived run.
"""

import asyncio
import shutil
import time
from pathlib import Path

from adapters.local.storage import DiskStorage
from core.graph import GraphContext, build_graph
from core.models import VideoJob
from tests.fakes import FakeLLMProvider, FakeRenderBackend, FakeSkillRegistry, FakeTTSProvider

SEGMENT_COUNT_TARGET_MS = 15 * 28 * 1000  # ~15 segments, a realistic 7-minute job
RUN_ROOT = Path("artifacts") / "_measure_segment_concurrency"


async def main() -> None:
    if RUN_ROOT.exists():
        shutil.rmtree(RUN_ROOT)
    storage_root = RUN_ROOT / "storage"

    job = VideoJob(
        job_id="measure-1", topic="measurement run", target_duration_ms=SEGMENT_COUNT_TARGET_MS
    )
    context = GraphContext(
        llm=FakeLLMProvider(),
        tts=FakeTTSProvider(),
        storage=DiskStorage(storage_root),
        skills=FakeSkillRegistry(),
        render=FakeRenderBackend(),
        working_dir=RUN_ROOT / "work",
    )

    graph = build_graph()  # no checkpointer: this run measures throughput, not resume
    config = {"configurable": {"thread_id": job.job_id}}

    started = time.perf_counter()
    result = await graph.ainvoke({"job": job, "segments": {}}, config, context=context)
    elapsed = time.perf_counter() - started

    print(f"segments: {job.segment_count}")
    print(f"elapsed:  {elapsed:.3f}s")
    print(f"per segment: {elapsed / job.segment_count * 1000:.1f}ms")
    assert result["job"].status.value == "succeeded"

    shutil.rmtree(RUN_ROOT)


if __name__ == "__main__":
    asyncio.run(main())
