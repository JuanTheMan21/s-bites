"""Deciding when Tier 0/1 capture a still.

Before T18K, ``rendering/reveal.py`` sampled Tier 1's four states at fixed, evenly-spaced
timestamps with no idea a caption cue or a block's own item reveal existed. A 9-cue segment can
only ever show 4 of them, and ``xfade`` visibly smears one cue's text into the next -- D161's
root cause for "complete wrong subtitles" on every Tier-1 segment (which today means every
geometry-failure fallback, see ``core/graph/nodes/render_scene.py``).

This module is pure and has no I/O: ``rendering/compose.py`` builds the plan (it already has the
cues and every block's resolved timing in hand) and writes it as a small JSON sidecar next to
``index.html``; ``rendering/reveal.py`` reads it back. A sidecar, not a changed return type on
``compose_scene``, because ``compose_scene`` already writes more than one file into its
composition directory (``gsap.min.js``) and ``hyperframes lint``/``check`` only care about the
entry file's name and location (D60), never about siblings.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

# The filename the sidecar lives under, next to `index.html` -- same directory ``compose_scene``
# already writes `gsap.min.js` into.
STILL_PLAN_FILENAME = "still_plan.json"

# Mirrors reveal.py's pre-T18K constants exactly -- the "settle past the pre-animation blank
# frame" reasoning is unchanged, only *which* instants get sampled after that point is new.
SETTLE_S_CAP = 1.5
SETTLE_FRACTION = 0.12

# Two samples closer together than this are the same visual moment -- collapsing them avoids a
# near-zero-duration crossfade segment ffmpeg would otherwise choke on.
MIN_SPACING_S = 0.2

# A hard ceiling on stills per segment, so a segment with an unusually dense cue schedule cannot
# make Tier 1 capture cost unbounded. Cue boundaries are never dropped to make room (correctness
# over budget, the user's own stated constraint) -- only candidate (non-cue) samples are thinned.
MAX_STILLS = 24


@dataclass(frozen=True, slots=True)
class StillSample:
    """One capture instant. ``is_cue_boundary`` marks an instant where the caption band is about
    to change text -- ``rendering/reveal.py`` uses it to pick a hard cut over a real crossfade for
    the transition landing on this instant, so two different captions are never blended into one
    another mid-transition."""

    at_s: float
    is_cue_boundary: bool


def settle_seconds(duration_s: float) -> float:
    """The instant before which nothing is sampled -- every template's entrance only starts
    tweening in around t=0.1-0.5s, so a literal t=0 capture is the pre-animation blank frame."""
    return min(SETTLE_S_CAP, duration_s * SETTLE_FRACTION)


def _clamp(t: float, *, low: float, high: float) -> float:
    return min(max(t, low), high)


def plan_still_samples(
    cue_starts_s: list[float],
    candidate_times_s: list[float],
    *,
    duration_s: float,
) -> list[StillSample]:
    """Merge caption-cue starts (mandatory) with block reveal candidates (optional) into a
    sorted, deduped, capped list of capture instants -- always ending at ``duration_s``, the
    fully-settled end state Tier 0/1 have always shown last (D79).

    Every element of ``cue_starts_s`` is guaranteed to appear (clamped into the settled window,
    never dropped even past ``MAX_STILLS``) -- caption correctness is the constraint the user set;
    item-reveal candidates are the nice-to-have that yield first under budget pressure.
    """
    settle_s = settle_seconds(duration_s)
    end_s = max(duration_s, settle_s)

    cues = sorted({_clamp(t, low=settle_s, high=end_s) for t in cue_starts_s})
    candidates = sorted({_clamp(t, low=settle_s, high=end_s) for t in candidate_times_s})

    samples: list[StillSample] = [StillSample(t, True) for t in cues]
    for t in candidates:
        if not any(abs(t - s.at_s) < MIN_SPACING_S for s in samples):
            samples.append(StillSample(t, False))

    if not any(abs(s.at_s - end_s) < MIN_SPACING_S for s in samples):
        samples.append(StillSample(end_s, False))

    samples.sort(key=lambda s: s.at_s)
    samples = _dedupe_adjacent(samples)

    if len(samples) > MAX_STILLS:
        samples = _thin_to_budget(samples)

    return samples


def _dedupe_adjacent(samples: list[StillSample]) -> list[StillSample]:
    """A second sort-then-merge pass: appending the forced end-state sample above can land it
    within ``MIN_SPACING_S`` of an already-sorted neighbour. A cue boundary always wins a merge
    against a candidate, since it carries information the candidate does not."""
    deduped: list[StillSample] = []
    for sample in samples:
        if deduped and abs(sample.at_s - deduped[-1].at_s) < MIN_SPACING_S:
            if sample.is_cue_boundary and not deduped[-1].is_cue_boundary:
                deduped[-1] = sample
            continue
        deduped.append(sample)
    return deduped


def _thin_to_budget(samples: list[StillSample]) -> list[StillSample]:
    """Drop candidate (non-cue) samples, evenly, until the list fits ``MAX_STILLS``. Every cue
    boundary, plus the first and last sample, always survives -- if cue boundaries alone exceed
    the budget, the budget loses, not correctness."""
    mandatory = {i for i, s in enumerate(samples) if s.is_cue_boundary} | {0, len(samples) - 1}
    droppable = [i for i in range(len(samples)) if i not in mandatory]
    allowed_extra = max(0, MAX_STILLS - len(mandatory))

    if allowed_extra >= len(droppable):
        keep_droppable = set(droppable)
    else:
        step = len(droppable) / allowed_extra if allowed_extra else float("inf")
        keep_droppable = {droppable[int(i * step)] for i in range(allowed_extra)}

    return [s for i, s in enumerate(samples) if i in mandatory or i in keep_droppable]


def write_still_plan(dest_dir: Path, samples: list[StillSample]) -> None:
    """Write ``samples`` as JSON beside ``dest_dir/index.html``. Cheap and always written --
    Tier 0/2 renderers simply never read it back."""
    payload = [asdict(s) for s in samples]
    (dest_dir / STILL_PLAN_FILENAME).write_text(json.dumps(payload), encoding="utf-8")


def read_still_plan(dest_dir: Path) -> list[StillSample] | None:
    """The other half of ``write_still_plan``. Returns ``None`` when no sidecar exists -- the
    caller's own fallback (an unplanned, evenly-spaced sample set) is what ran before T18K and
    stays available for a composition directory this module never wrote into."""
    path = dest_dir / STILL_PLAN_FILENAME
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [
        StillSample(at_s=item["at_s"], is_cue_boundary=item["is_cue_boundary"]) for item in payload
    ]
