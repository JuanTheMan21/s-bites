"""How many frames a video of a given length is allowed to spend.

Separate from ``core/tier_resolver.py`` on purpose, and the split is by responsibility rather
than for line count: the resolver *spends* a budget, this decides *how large* one is. Nothing
here knows about tiers, and the resolver does not import this -- the caller calls both, passing
the answer from one into the other. That keeps T5's definition of done literally true: the
resolver imports stdlib and ``core.models``, nothing else.

Like the resolver, this reads no configuration. ``FRAME_BUDGET`` lives in the environment and is
read at the edge; both the base and the ceiling arrive here as parameters.
"""

from core.models import DEFAULT_TARGET_DURATION_MS


def scale_frame_budget(
    base_frames: int, target_duration_ms: int, *, max_multiple: float = 2.0
) -> int:
    """Scale a budget calibrated for a default-length video to the length actually requested.

    ``base_frames`` is what a ``DEFAULT_TARGET_DURATION_MS`` video gets; longer requests get
    proportionally more, up to ``max_multiple`` of the base. Shorter requests scale down the
    same way, so a two-minute video does not get a seven-minute video's render time.

    The cap is the whole point. A frame budget is really a *render-time* budget -- measured at
    ~17 frames/sec with ``--workers 4`` (T18A; corrects D16's 1.7-2.7 fps, which was sampled on
    a 3-second render dominated by cold-start overhead) -- so scaling linearly with no ceiling
    still turns a long enough video into a long render. Not scaling at all spreads the same
    frames across three times the segments until everything lands on Tier 0 and the tier system
    stops meaning anything.
    """
    if base_frames < 0:
        raise ValueError(f"base_frames cannot be negative, got {base_frames}")
    if max_multiple < 1:
        raise ValueError(f"max_multiple cannot be below 1, got {max_multiple}")
    multiple = min(max(target_duration_ms, 0) / DEFAULT_TARGET_DURATION_MS, max_multiple)
    return round(base_frames * multiple)
