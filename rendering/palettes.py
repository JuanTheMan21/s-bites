"""One color family per motif, so a video's palette matches the tone ``plan_visuals`` chose for
it instead of being an arbitrary hash of the job id.

T18B: replaces the six job-id-hashed palettes (D95/T18A) with three motif-keyed families --
``core.block_types.MotifName`` is chosen once per video by ``core/graph/nodes/visual_plan.py``,
matched to the topic, so palette variety now comes from a real editorial choice instead of a
coin flip. Still keeps the semantic split every block partial relies on
(``--accent-primary`` = emphasis, ``--accent-secondary`` = structure) -- only the concrete
colors change per family, never what the two tokens mean.
"""

from pydantic import BaseModel, ConfigDict

from core.block_types import MotifName


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


# Each pair was picked, then checked, against the same two rules D95 established:
#   1. fg on bg clears WCAG AA (4.5:1) for body text -- `hyperframes check --contrast` verifies
#      this for real against the rendered composition, this is the human sanity check before that.
#   2. accent_primary and accent_secondary read as visibly different hues from each other and
#      from fg/fg_muted, so the emphasis/structure split stays legible, not just present.
# Blueprint: light paper background, schematic connectors -- the real fix for D95's "still reads
# navy blue" finding, which no dark palette (however many of them) could ever answer.
# Terminal: warm dark charcoal, zero blue in either accent -- a genuinely different hue family
# from the old amber/blue default, for topics (security, systems) that suit a console feel.
# Broadcast: light neutral, one bold accent -- a third distinct register, closer to a
# lower-third/news-graphics look than either of the other two.
MOTIF_PALETTES: dict[MotifName, Palette] = {
    MotifName.BLUEPRINT: Palette(
        name="blueprint",
        bg="#eef1f6",
        fg="#101826",
        fg_muted="#5b6472",
        accent_primary="#c2410c",
        accent_secondary="#1d4ed8",
    ),
    MotifName.TERMINAL: Palette(
        name="terminal",
        bg="#141110",
        fg="#f5efe6",
        fg_muted="#a89a89",
        accent_primary="#ffb703",
        accent_secondary="#4ade80",
    ),
    MotifName.BROADCAST: Palette(
        name="broadcast",
        bg="#f7f6f2",
        fg="#141414",
        fg_muted="#6b6862",
        accent_primary="#dc2626",
        accent_secondary="#0f172a",
    ),
}

# The default for a caller with no motif context yet (a bare template test) -- kept as the
# original amber-on-near-black identity so nothing that predates motifs changes appearance.
_DEFAULT_PALETTE = Palette(
    name="amber_blue",
    bg="#08080a",
    fg="#eeeeee",
    fg_muted="#8b8b93",
    accent_primary="#ffb703",
    accent_secondary="#4fa8ff",
)


def select_palette(motif: MotifName | None) -> Palette:
    """The palette for ``motif``. ``motif=None`` (a caller with no scene context, e.g. a bare
    template test) always gets the original amber-on-near-black default."""
    if motif is None:
        return _DEFAULT_PALETTE
    return MOTIF_PALETTES[motif]
