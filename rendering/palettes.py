"""Per-job color palettes, so consecutive videos do not all read as the same amber-on-black.

T18A: D95 replaced glow/gradient "Data Drift" with two flat, semantic tokens
(``--accent-primary`` = emphasis, ``--accent-secondary`` = structure) but left both hardcoded, so
every video -- regardless of topic -- used the identical amber/blue pair. D95's own closing note
flagged this as still reading "blue-dominant" once ``diagram_flow`` (a heavy structure-token user)
is frequent. This module keeps the semantic split every template already relies on, but gives it
several hand-picked, contrast-checked color pairs instead of one.

Selection is **deterministic from job_id**, not random: the same job resumed across a checkpoint,
or re-rendered for debugging, must land on the same palette every time -- a random pick would make
``diagram_flow``'s marker fix (D94) or a template bug look intermittent across runs of the same job.
"""

import hashlib

from pydantic import BaseModel, ConfigDict


class Palette(BaseModel):
    """The five tokens ``_tokens.html``'s ``tokens_style()`` interpolates into ``:root``.

    Field names match the CSS custom properties 1:1 (underscores for hyphens) so
    ``rendering/compose.py`` can hand the model straight to Jinja without a translation layer.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    bg: str
    fg: str
    fg_muted: str
    accent_primary: str
    accent_secondary: str


# Every pair below was picked, then checked, against these two rules:
#   1. fg on bg clears WCAG AA (4.5:1) for body text -- `hyperframes check --contrast` verifies
#      this for real against the rendered composition, this is the human sanity check before that.
#   2. accent_primary and accent_secondary read as visibly different hues from each other and
#      from fg/fg_muted, so the emphasis/structure split (D95) stays legible, not just present.
# "amber_blue" is D95's original pair, kept as the default/first entry so nothing before this task
# silently changes appearance if a caller never opts into selection.
PALETTES: tuple[Palette, ...] = (
    Palette(
        name="amber_blue",
        bg="#08080a",
        fg="#eeeeee",
        fg_muted="#8b8b93",
        accent_primary="#ffb703",
        accent_secondary="#4fa8ff",
    ),
    Palette(
        name="coral_teal",
        bg="#0a0908",
        fg="#f2ede6",
        fg_muted="#94897d",
        accent_primary="#ff6b5e",
        accent_secondary="#2dd4bf",
    ),
    Palette(
        name="violet_lime",
        bg="#0a0a0f",
        fg="#ece9f5",
        fg_muted="#8d89a0",
        accent_primary="#c084fc",
        accent_secondary="#a3e635",
    ),
    Palette(
        name="rose_cyan",
        bg="#0b0709",
        fg="#f5e9ec",
        fg_muted="#9c8890",
        accent_primary="#fb7185",
        accent_secondary="#22d3ee",
    ),
    Palette(
        name="gold_indigo",
        bg="#09080c",
        fg="#efeced",
        fg_muted="#928da3",
        accent_primary="#facc15",
        accent_secondary="#818cf8",
    ),
    Palette(
        name="ember_seafoam",
        bg="#0a0807",
        fg="#f1ece5",
        fg_muted="#998f80",
        accent_primary="#fb923c",
        accent_secondary="#5eead4",
    ),
)


def select_palette(job_id: str | None) -> Palette:
    """The palette for ``job_id`` -- stable across every call with the same id, spread across
    every call with different ids. ``job_id=None`` (a caller with no job context, e.g. a bare
    template test) always gets the original ``amber_blue`` default.
    """
    if job_id is None:
        return PALETTES[0]
    digest = hashlib.sha256(job_id.encode("utf-8")).digest()
    return PALETTES[digest[0] % len(PALETTES)]
