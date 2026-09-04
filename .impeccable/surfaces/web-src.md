---
version: 1
slug: "web-src"
primary_target: "web/src"
related_targets: []
---

## Direction contract

THESIS: The product is a clip bin filling in live, not a generic dashboard's progress bar — it
refuses the six-equal-widget default every comparable AI video tool ships.

OWN-WORLD: A broadcast/NLE production-timeline vocabulary (Premiere/Descript/Resolve) — a
horizontal clip track where each segment is a thumbnail-style block, JetBrains Mono timecodes
throughout (already in stack), a "REC ●" live indicator during active phases, warm paper/ink tokens
kept from DESIGN.md (brand-safe), one accent reserved for "recording/live," tier color restored as
literal clip-block fill (fixes the `domain/tier.ts` bug).

STORY: A visitor watches their topic become a video the way an editor watches a timeline fill with
clips — segments appear as blocks on the track immediately, each block's fill/label completing with
real duration/tier the instant the backend reports it (D137: never simulated).

FIRST VIEWPORT: composer unchanged (D141) at top, framed as opening a new project; directly beneath,
a horizontal clip track spans full width with a moving playhead/timecode readout; segment blocks
sit on that track (not a card grid), each showing its real tier as fill color and real duration once
known; a "Recording narration..." / phase-live line sits above the track like a REC indicator.

FORM: Impeccable's Pick — the user's explicit, informed choice of the top-ranked grounded candidate
(1 of 7) over the tool's anti-rut assignment (which landed on #5, the caption-editor world). Seed
key 3dde5962; network roll degraded (Node fetch blocked; curl succeeded), built from the grounded
list per the skill's documented fallback. Full 7-candidate list stays on record below.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the
verdict, DESIGN.md, and every shipping raster carrying its provenance.

---

## Grounded candidate list (ranked by resonance, for the record)

1. **Broadcast/production timeline** (Premiere/Descript/Resolve) — clips-on-a-track, waveform,
   playhead, timecode. The product's own mechanism (duration-locked segments) IS a timeline.
   ← CHOSEN (Impeccable's Pick, user-selected over the assignment)
2. **Mission control / ops telemetry board** — status lights, monospace readouts, phase boards.
   Strongest fit for the loading screen specifically.
3. **Instructional-design storyboard/script binder** — numbered scene cards, timecode column.
   Validates the existing segment-card pattern with real professional vocabulary.
4. **Radio/podcast control-room channel strip** — VU meters, on-air light. Literalizes the
   "we measure real audio" claim.
5. **Subtitle/caption editor** (Rev/YouTube Studio) — waveform + karaoke-timed text blocks.
   ← the tool's anti-rut assignment; not chosen.
6. **Split-flap departure board** — playful at-a-glance status; weak for dense states.
7. **Slate & take log** — literal "take" numbering; low resonance for the self-learner persona.

Families spanned: creative-pro software (1,5), operations dashboard (2), print/paper artifact
(3,7), physical AV/signage (4,6).

Excluded as the category rut (never candidates): dark-mode neon/glassmorphism "AI tool" default,
and its predictable opposite, a sterile flat enterprise SaaS dashboard.
