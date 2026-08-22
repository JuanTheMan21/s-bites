"""The contract for narration, and for the measurement every timing decision rests on."""

from abc import ABC, abstractmethod
from pathlib import Path


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
    ) -> tuple[Path, int]:
        """Narrate ``text`` into ``dest``. Returns ``(audio_path, duration_ms)``.

        ``duration_ms`` is **milliseconds**, measured from the audio that was produced --
        never estimated from text length or speaking rate.

        ``dest``'s parent directory is created if absent and an existing file there is
        overwritten. The returned path equals ``dest``.

        ``voice`` selects a named voice; ``None`` means the adapter's configured default.

        Raises:
            RateLimited: the backend throttled the request and retries were exhausted.
            ProviderUnavailable: the backend could not be reached.
            ProviderMisconfigured: the backend refused the credentials, or has no such
                voice. An unknown ``voice`` fails identically on every attempt, which makes
                it a misconfiguration rather than an outage.
        """
