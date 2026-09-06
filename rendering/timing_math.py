"""Pure array-timing math shared by ``rendering/block_timing.py``'s item/step resolution -- no
schema, no block-type knowledge, just "given a list of resolved-or-missing instants, fill the
gaps" and "given a list of instants, force them non-decreasing."

Split out of ``block_timing.py`` (T18K) once the D163 clamp fix would have pushed that module
over the 200-line ceiling -- this module holds the two array-only helpers; ``block_timing.py``
stays the block-schema-aware orchestration layer that calls them.
"""

import itertools


def interpolate_missing(
    resolved: list[float | None], *, entrance_start: float, end_s: float
) -> list[float]:
    """Fill in every ``None`` by linear interpolation against ``entrance_start``/``end_s`` as
    virtual bookend anchors -- so a gap before the first real match, a gap after the last, and a
    gap between two matches are all the same one-loop case, and every returned time falls inside
    the block's own visible window regardless of how many (or how few) items actually matched.

    All-unmatched degrades to an even spread across the window (T18J's cascade replacement);
    a single unmatched item lands at the window's midpoint.
    """
    n = len(resolved)
    if n == 0:
        return []
    end_s = max(end_s, entrance_start)

    points: list[tuple[int, float]] = [(-1, entrance_start)]
    points.extend((i, t) for i, t in enumerate(resolved) if t is not None)
    points.append((n, end_s))

    out = [entrance_start] * n
    for (i1, t1), (i2, t2) in itertools.pairwise(points):
        gap = i2 - i1
        for k in range(i1 + 1, i2):
            out[k] = t1 + (t2 - t1) * (k - i1) / gap

    for i, t in enumerate(resolved):
        if t is not None:
            out[i] = t
    return out


def clamp_non_decreasing(starts: list[float]) -> list[float]:
    """Force ``starts`` to be non-decreasing in the given (structural draw) order -- a running
    max, not a re-sort. D163: a node whose anchor phrase matches earlier narration than the node
    before it must still visually enter no earlier than that previous node."""
    clamped: list[float] = []
    running_max = float("-inf")
    for t in starts:
        running_max = max(running_max, t)
        clamped.append(running_max)
    return clamped
