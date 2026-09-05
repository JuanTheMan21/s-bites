"""Deterministic post-processing on one block's own AUTHORED content, applied right after
``fill_block``'s ``generate_with_bounded_retries`` call returns -- the content-level sibling of
``core/scene_normalize.py`` (which normalizes a scene's SHAPE: layout and block count, decided
before any content exists). This module fixes up a single block's payload once it exists.

T18I: ``SequenceDiagramSlots.messages``'s own schema description asks for "at most 3" (a real,
watched render found more reads as hard to follow -- the user's own words, on a TCP handshake),
but strict-mode structured output cannot enforce a list length (D29's own precedent: `enum`
survives strict mode, range/count keywords do not) -- so a model that ignores the wording still
returns six or eight messages. Truncating here, rather than rejecting and re-asking, is the
deliberate choice: a message COUNT is not content quality the way a geometry finding is, there is
nothing here for an LLM to get right on a second try that it could not get right on the first, and
a re-ask would spend a whole extra call to ask for exactly the same words, just fewer of them --
keeping the model's own first 3 (its own narration-order choice of what matters most) is strictly
cheaper and no less correct.
"""

from typing import Any

from core.block_types import BlockType

# The user's own stated ceiling, verbatim: "maybe like 3 horizontal lines max not more than that
# if it's more than three then some other visual representation is required."
_MAX_SEQUENCE_MESSAGES = 3


def normalize_block_payload(block_type: BlockType, payload: dict[str, Any]) -> dict[str, Any]:
    """Fix up one block's own authored payload, deterministically. A block type this module has
    no rule for is returned unchanged -- this is a small, explicit registration list (the same
    "no-op for anything not named" shape ``ALLOWED_BLOCKS``/``TIER_SUPPORT`` already are), not a
    catch-all."""
    if block_type == BlockType.SEQUENCE_DIAGRAM:
        messages = payload.get("messages")
        if isinstance(messages, list) and len(messages) > _MAX_SEQUENCE_MESSAGES:
            payload = {**payload, "messages": messages[:_MAX_SEQUENCE_MESSAGES]}
    return payload
