"""The contract for narration, and for the measurement every timing decision rests on."""

from abc import ABC, abstractmethod
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class WordMark(BaseModel):
    """One spoken word, and when it landed in its segment's narration audio.

    T18A: what makes a caption or an on-screen reveal track the actual voice instead of an
    evenly-spaced guess. Contract vocabulary, not a domain concept -- same precedent as
    ``SkillPack``/``QueuedJob`` living beside the interface they belong to rather than in
    ``core/`` (D22's boundary runs one way: ``core`` may import ``interfaces``, never the
    reverse). ``offset_ms``/``duration_ms`` are relative to the *start of this segment's own
    audio*, not the final concatenated video.
    """

    model_config = ConfigDict(extra="forbid")

    text: str
    offset_ms: int = Field(ge=0)
    duration_ms: int = Field(ge=0)


class SynthesisResult(BaseModel):
    """What ``TTSProvider.synthesize`` hands back: the audio it wrote, its measured length, and
    -- when the backend can report them -- the words within it.

    ``words`` may be **empty**. A backend with no word-boundary reporting (Kokoro, eventually;
    ``hyperframes transcribe`` is the documented fallback for one -- see T18A's decisionlog
    entry) is still a valid ``TTSProvider``: every consumer must degrade to an even stagger
    rather than assume this list is populated. ``duration_ms`` is unaffected either way: it is
    always measured from the file (Invariant 1, D54), never summed from word marks.
    """

    model_config = ConfigDict(extra="forbid")

    audio_path: Path
    duration_ms: int = Field(ge=0)
    words: list[WordMark] = Field(default_factory=list)


class TTSProvider(ABC):
    """Narrates text to an audio file and reports how long the result actually is.

    The duration in the return value is the load-bearing part of this interface. Scene
    timing derives from measured audio, never from an LLM estimate or a words-per-minute
    heuristic, because a scene that is 300ms short of its narration puts every following
    segment further out of sync. Returning ``duration_ms`` alongside the audio is what makes
    that rule structural: ``scene_author`` takes the measurement as a required argument, so
    authoring a scene before its narration exists is a type error rather than a review note.
    """

    @abstractmethod
    async def synthesize(
        self, text: str, dest: Path, *, voice: str | None = None
    ) -> SynthesisResult:
        """Narrate ``text`` into ``dest``. Returns a ``SynthesisResult``.

        ``duration_ms`` is **milliseconds**, measured from the audio that was produced --
        never estimated from text length or speaking rate. ``audio_path`` equals ``dest``.

        ``dest``'s parent directory is created if absent and an existing file there is
        overwritten.

        ``voice`` selects a named voice; ``None`` means the adapter's configured default.

        Raises:
            RateLimited: the backend throttled the request and retries were exhausted.
            ProviderUnavailable: the backend could not be reached.
            ProviderMisconfigured: the backend refused the credentials, or has no such
                voice. An unknown ``voice`` fails identically on every attempt, which makes
                it a misconfiguration rather than an outage.
        """
