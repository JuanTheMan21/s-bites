"""``python cli.py "<topic>"`` -- the fastest inner loop this project has (D8), and the thing
T18's DoD is verified against: outline, narrate, tier, author every scene, render, mux, and concat,
all the way to one playable MP4, honoring ``RUNTIME_ENV``.

Not under ``core/``, so the boundary hook does not restrict it -- imports ``langgraph`` directly,
the same as ``tests/test_graph_pipeline.py`` already does, with no wrapper needed.
"""

import argparse
import asyncio
import logging
import os
import time
import uuid
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from config import build_adapters, close_adapters
from core.graph import GraphContext, build_graph
from core.models import DEFAULT_TARGET_DURATION_MS
from core.video_job import VideoJob

# Azure Speech S0's published rate (D48) -- used only for the estimated-cost line in the summary
# below, never for anything that decides behaviour.
AZURE_SPEECH_S0_USD_PER_MILLION_CHARS = 15.0


def _required_int(name: str) -> int:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is not set. Copy .env.example to .env and fill it in.")
    try:
        return int(value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer, got {value!r}") from exc


def _print_summary(job: VideoJob, *, elapsed_s: float) -> None:
    spread = Counter(segment.tier for segment in job.segments)
    total_chars = sum(len(segment.narration or "") for segment in job.segments)
    estimated_tts_usd = total_chars / 1_000_000 * AZURE_SPEECH_S0_USD_PER_MILLION_CHARS

    print(f"\nsegments: {len(job.segments)}")
    print(
        "tiers:    " + "  ".join(f"T{int(tier)}={count}" for tier, count in sorted(spread.items()))
    )
    print(f"elapsed:  {elapsed_s:.1f}s")
    print(
        f"narration: {total_chars} characters (~${estimated_tts_usd:.3f} estimated TTS cost, "
        "Azure Speech S0 rate -- LLM cost is not itemized here; run /costs for the real total)"
    )
    # T18I: the production failure story's own signal -- previously a geometry failure crashed
    # the whole job with nothing telling anyone which segment or which finding. A clean job (the
    # common case) prints nothing here; degraded_segments being non-empty is itself the news.
    if job.degraded_segments:
        print(f"\ndegraded segments: {len(job.degraded_segments)}")
        for outcome in job.degraded_segments:
            fallback_note = "fell back to title card" if outcome.fallback_used else "re-authored"
            print(
                f"  segment {outcome.segment_index}: {fallback_note} after {outcome.attempts} "
                f"attempt(s) -- findings: {outcome.finding_codes}"
            )


async def _run(topic: str, *, target_duration_ms: int, job_id: str) -> VideoJob:
    load_dotenv()
    frame_budget = _required_int("FRAME_BUDGET")
    fps = _required_int("FPS")

    job = VideoJob(job_id=job_id, topic=topic, target_duration_ms=target_duration_ms)
    working_dir = Path("artifacts") / "_cli_run" / job.job_id
    # AsyncSqliteSaver.from_conn_string opens the file with sqlite3.connect, which does not
    # create missing parent directories -- every graph test gets this for free from pytest's
    # tmp_path fixture, but a fresh job_id here means working_dir genuinely does not exist yet.
    working_dir.mkdir(parents=True, exist_ok=True)

    adapters = build_adapters()
    try:
        context = GraphContext(
            llm=adapters.llm,
            tts=adapters.tts,
            storage=adapters.storage,
            skills=adapters.skills,
            render=adapters.render,
            working_dir=working_dir,
            frame_budget=frame_budget,
            fps=fps,
        )
        async with AsyncSqliteSaver.from_conn_string(
            str(working_dir / "checkpoints.sqlite")
        ) as saver:
            graph = build_graph(saver)
            config = {"configurable": {"thread_id": job.job_id}}
            # T18I: a real bug, found running this task's own closing render -- passing a fresh
            # {"job": ..., "segments": {}} input on EVERY invocation (as this always did) tells
            # LangGraph to (re)initialize state, which silently overwrites an already-checkpointed
            # run's progress with a blank one instead of resuming it -- the graph then reruns from
            # plan_segments regardless of how far a prior attempt got. tests/test_graph_resume.py's
            # own resume calls already do this correctly (`ainvoke(None, config, ...)`); this was
            # simply never applied here. aget_state's own values are non-empty only once a run has
            # actually reached its first checkpoint (after plan_segments), so this is the same
            # "does a checkpoint already exist" signal every LangGraph resume pattern relies on.
            existing = await graph.aget_state(config)
            resuming = bool(existing.values)
            print(f"{'resuming' if resuming else 'starting'} job {job.job_id}")
            graph_input = None if resuming else {"job": job, "segments": {}}
            result = await graph.ainvoke(graph_input, config, context=context, durability="sync")
        finished: VideoJob = result["job"]

        local_final = working_dir / finished.job_id / "final.mp4"
        local_srt = working_dir / finished.job_id / "final.srt"
        print(f"\nlocal copy:  {local_final}")
        if local_srt.exists():
            print(f"subtitles:   {local_srt}")
        if finished.video_key is not None:
            print(f"storage url: {await adapters.storage.url(finished.video_key)}")
        return finished
    finally:
        await close_adapters(adapters)


async def main() -> None:
    # T18E: without this, core/graph/node_timing.py's per-node start/elapsed logging and
    # adapters/azure/llm_provider.py's retry logging never reach the console -- Python's own
    # "handler of last resort" only surfaces WARNING and above when nothing has configured
    # logging, which is why a retry line showed up in a real render but node timing never did
    # (confirmed live: neither run this task verified against showed a single "node ... started"
    # line). This is the fix, not a new feature -- E5's own DoD promised visible timing.
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "topic",
        nargs="?",
        default=None,
        help="the prompt as a user would type it -- omit it to be prompted on stdin",
    )
    parser.add_argument(
        "--target-duration-ms",
        type=int,
        default=DEFAULT_TARGET_DURATION_MS,
        help="requested video length; segment count and frame budget both derive from it",
    )
    parser.add_argument(
        "--job-id", default=None, help="defaults to a fresh uuid4 -- pass one to resume a run"
    )
    args = parser.parse_args()

    # T18A: a topic-less invocation is the local entrypoint D92/T18A asked for -- ugly is fine,
    # this is not the FastAPI+React product (T19-T28), it is the fastest way to get a real video
    # out of this machine without hand-mixing adapters in a scratch script.
    topic = args.topic
    if topic is None:
        topic = input("topic: ").strip()
        if not topic:
            raise SystemExit("no topic given")

    job_id = args.job_id or str(uuid.uuid4())
    started = time.perf_counter()
    finished = await _run(topic, target_duration_ms=args.target_duration_ms, job_id=job_id)
    _print_summary(finished, elapsed_s=time.perf_counter() - started)


if __name__ == "__main__":
    asyncio.run(main())
