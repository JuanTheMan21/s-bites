"""``WordMark``/``SynthesisResult`` re-exported for ``core/models.py``'s convenience.

They are defined in ``interfaces/tts_provider.py`` -- contract vocabulary, the same precedent as
``SkillPack``/``QueuedJob`` (D22: ``core`` may import ``interfaces``, never the reverse) -- not
domain concepts that belong under ``core/``. This module exists only so ``core.models.Segment``
and anything importing ``core`` can reach ``WordMark`` without naming ``interfaces`` directly in
every call site, mirroring how ``core/__init__.py`` re-exports pieces of several modules already.
"""

from interfaces.tts_provider import SynthesisResult, WordMark

__all__ = ["SynthesisResult", "WordMark"]
