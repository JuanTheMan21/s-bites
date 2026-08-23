"""Measuring a synthesised audio file. The number Invariant 1 rests on.

Lives at the root of ``adapters/`` for the same reason ``adapters/skill_pack_format.py`` does:
the measurement is identical wherever the audio came from. Azure Speech and Kokoro produce very
different files by very different means, and both are then measured by *this* function -- so
"``duration_ms`` means the same thing on both stacks" is structural rather than a parity note
someone has to check.

**Why measure the file rather than believe the synthesiser.** Azure Speech's SDK reports an
``audio_duration`` and it is, in practice, correct -- T8's smoke run had it agree with ``ffprobe``
to the millisecond. But a reported duration and a measured one are different *kinds* of number,
and the whole of Invariant 1 is that scene timing derives from the second kind. Taking the SDK's
word for it would work until an adapter appeared whose SDK did not offer one, at which point that
adapter would measure and the other would report, and the two would agree right up until they
did not. D38 made exactly this argument about ``FakeTTSProvider``.

``wave`` rather than shelling out to ``ffprobe``: this runs once per segment on every job, a
subprocess per call is real cost, and stdlib gives the identical answer for a RIFF WAV. The
adapters pin their output format to RIFF precisely so that stays true. ``ffprobe`` remains the
independent check in ``scripts/verify_azure.py`` and in T10's live test, which is where an
independent check belongs -- outside the code being checked.
"""

import contextlib
import wave
from pathlib import Path


def wav_duration_ms(path: Path) -> int:
    """Milliseconds of audio in the RIFF WAV at ``path``, rounded to the nearest millisecond.

    Raises:
        ValueError: the file is not a readable RIFF WAV, or claims a zero frame rate. Not an
            ``AdapterError``: the backend answered and we wrote the bytes ourselves, so a file
            that will not parse is our bug or a truncated write, not the provider misbehaving.
        OSError: the file could not be read at all.
    """
    try:
        with contextlib.closing(wave.open(str(path), "rb")) as audio:
            frames, rate = audio.getnframes(), audio.getframerate()
    except wave.Error as exc:
        raise ValueError(f"{path} is not a readable RIFF WAV: {exc}") from exc

    if rate <= 0:
        # A zero frame rate would make the division below raise ZeroDivisionError several frames
        # from anything that names the file, which is a bad afternoon for whoever hits it.
        raise ValueError(f"{path} reports a frame rate of {rate}, so it cannot be measured")

    return round(frames / rate * 1000)
