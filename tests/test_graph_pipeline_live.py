"""The full graph against the real local render backend -- the mixed-tier concat risk flagged in
T18's plan, exercised for real: does ``mux/concat_segments.py``'s crossfade concat actually
tolerate a Tier 0 clip (encoded by this project's own ``mux/frames_to_clip.py``) and a Tier 2 clip
(encoded by the HyperFrames CLI, D15) sitting in the same ``xfade``/``acrossfade`` chain?

``local_live``, following ``test_render_segment_live.py``'s shape: real
``PlaywrightHyperFramesRenderBackend``, ``aclose()`` in ``finally``. LLM and TTS stay fake -- this
tests the render/mux/concat path, not Azure, so there is no reason to spend real money proving it.

Both segments share one visual intent and one measured duration, deliberately: the ``author_scene``
and ``synthesize_segment`` fan-outs are concurrent, so the order either fake's queue gets popped in
is not guaranteed to match segment index -- identical entries make that irrelevant rather than
flaky, the same reasoning ``tests/graph_pipeline_fixtures.py::slot_payloads`` already documents.
``tests/graph_pipeline_live_fixtures.py`` builds the seeded LLM/skills this file consumes -- split
out once the T18E annotations addition pushed this file over the 200-line ceiling.
"""

from pathlib import Path

import pytest

from core.graph import GraphContext, build_graph
from core.models import Tier
from core.video_job import VideoJob
from mux.concat_segments import DEFAULT_TRANSITION_S
from tests.fakes import FakeStorage, FakeTTSProvider
from tests.graph_pipeline_live_fixtures import seeded_llm, seeded_skills

pytestmark = pytest.mark.local_live

DURATION_MS = 2_000
# Comfortably above 2x mux.concat_segments.DEFAULT_TRANSITION_S (0.5s) -- a duration right at
# that boundary made the one crossfade transition below too tight to render reliably.
#
# T18C/D107: the original target here was {Tier.STATIC, Tier.ANIMATED}, discovered to be
# unreachable at any safe duration for any segment count or importance pairing -- REVEAL's frame
# cost is a flat +7 over STATIC regardless of duration, while ANIMATED's cost is duration-scaled
# and always far larger at a safe duration, so a segment that fails REVEAL promotion never leaves
# enough remaining budget for another segment to reach ANIMATED. Retargeted to
# {Tier.REVEAL, Tier.ANIMATED} instead -- genuinely reachable, and still exercises the real
# two-clip crossfade concat this test actually cares about.
#
# FRAME_BUDGET chosen against core/tier_resolver.py's own arithmetic (checked by hand, not
# guessed): base cost is 2 (one STATIC frame per segment). Pass 1 promotes BOTH segments to
# REVEAL -- ASIDE's ideal tier is REVEAL, CRITICAL's ideal (ANIMATED) is >= REVEAL too -- costing
# +7 each (spent=16). Pass 2 promotes only CRITICAL to ANIMATED (ASIDE's ideal tier structurally
# excludes it from this pass, regardless of remaining budget); that costs +40 more
# (ceil(2000/1000*24)=48, minus the 8 it already cost at REVEAL) for a minimum of 56. Unlike the
# old target, there is no upper bound to stay under -- ASIDE can never be promoted past REVEAL no
# matter how large the budget grows -- so 80 is simply "comfortably above 56," not a boundary.
FRAME_BUDGET = 80
FPS = 24


async def test_a_mixed_tier_job_renders_muxes_and_concats_to_one_playable_video(
    tmp_path: Path,
) -> None:
    from adapters.local.render_backend import PlaywrightHyperFramesRenderBackend

    real_render = PlaywrightHyperFramesRenderBackend(
        quality="draft", max_attempts=1, timeout_s=90.0
    )
    storage = FakeStorage()
    job = VideoJob(job_id="live-mixed-tier", topic="a nice topic")

    try:
        context = GraphContext(
            llm=seeded_llm(),
            tts=FakeTTSProvider(durations=[DURATION_MS, DURATION_MS]),
            storage=storage,
            skills=seeded_skills(),
            render=real_render,
            working_dir=tmp_path / "work",
            frame_budget=FRAME_BUDGET,
            fps=FPS,
        )
        graph = build_graph()  # no checkpointer -- this test proves rendering, not resume
        config = {"configurable": {"thread_id": job.job_id}}

        result = await graph.ainvoke({"job": job, "segments": {}}, config, context=context)
    finally:
        await real_render.aclose()

    result_job: VideoJob = result["job"]
    assert result_job.status.value == "succeeded"

    tiers = {segment.tier for segment in result_job.segments}
    assert tiers == {Tier.REVEAL, Tier.ANIMATED}, (
        f"expected exactly one REVEAL and one ANIMATED segment to exercise the mixed-tier concat "
        f"path, got {tiers} -- FRAME_BUDGET's arithmetic above may need revisiting"
    )

    assert result_job.video_key is not None
    final_bytes = storage.objects[result_job.video_key]
    assert len(final_bytes) > 0

    final_path = tmp_path / "final.mp4"
    final_path.write_bytes(final_bytes)
    probe = _ffprobe(final_path)
    assert probe["stream_types"] == {"video", "audio"}
    # One crossfade transition (two clips) eats DEFAULT_TRANSITION_S off the naive sum, by design.
    expected_ms = 2 * DURATION_MS - DEFAULT_TRANSITION_S * 1000
    assert probe["duration_ms"] == pytest.approx(expected_ms, abs=300)


def _ffprobe(path: Path) -> dict:
    import subprocess

    streams = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "stream=codec_type",
            "-of",
            "csv=p=0",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    duration = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=nw=1:nk=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    return {
        "stream_types": {line.strip() for line in streams.splitlines() if line.strip()},
        "duration_ms": round(float(duration) * 1000),
    }
