---
name: skill-bites
description: Broadcast/NLE production-timeline console for a prompt-to-explainer-video pipeline — warm paper ground, one industrial accent, a real clip track standing in for the progress bar every comparable AI video tool ships.
colors:
  paper-0: "#fbfaf6"
  paper-1: "#f3f1e9"
  paper-2: "#e7e4d8"
  ink-900: "#16150f"
  ink-700: "#3a382e"
  ink-500: "#6b6759"
  ink-300: "#a8a392"
  accent: "#e8542f"
  accent-tint: "#ffe9e1"
  signal-run: "#2f6fe8"
  signal-ok: "#1e7a54"
  signal-warn: "#b8791c"
  signal-bad: "#c2331f"
  tier-0: "#6b6759"
  tier-1: "#2f6fe8"
  tier-2: "#e8542f"
  ring: "{colors.accent}"
typography:
  display:
    fontFamily: "Bricolage Grotesque Variable, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1.5rem – 1.875rem (text-2xl / text-3xl)"
    fontWeight: 400
    lineHeight: 1.2
    letterSpacing: "normal"
  title:
    fontFamily: "Bricolage Grotesque Variable, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1.125rem – 1.25rem (text-lg / text-xl)"
    fontWeight: 400
    lineHeight: 1.3
    letterSpacing: "normal"
  body:
    fontFamily: "Geist Variable, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.875rem (text-sm)"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
  label:
    fontFamily: "JetBrains Mono Variable, ui-monospace, monospace"
    fontSize: "0.6875rem – 0.75rem (11px / text-xs)"
    fontWeight: 500
    lineHeight: 1.3
    letterSpacing: "0.05em (tracking-wide)"
rounded:
  sm: "6px"
  md: "10px"
  lg: "16px"
  full: "9999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "20px"
  xl: "32px"
  page-y: "64px"
components:
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.paper-0}"
    rounded: "{rounded.md}"
    padding: "8px 16px"
  button-secondary:
    backgroundColor: "{colors.paper-0}"
    textColor: "{colors.ink-900}"
    rounded: "{rounded.md}"
    padding: "8px 16px"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.ink-700}"
    rounded: "{rounded.md}"
    padding: "8px 16px"
  card:
    backgroundColor: "{colors.paper-1}"
    textColor: "{colors.ink-900}"
    rounded: "{rounded.lg}"
    padding: "20px"
  pill:
    backgroundColor: "{colors.paper-2}"
    textColor: "{colors.ink-700}"
    rounded: "{rounded.full}"
    padding: "4px 10px"
---

# Design System: skill-bites

## Overview

**Creative North Star: "The Broadcast Timeline"**

T37 re-grounded the console in a broadcast/NLE production-timeline vocabulary (Premiere/Descript/
Resolve) rather than the six-equal-widget dashboard the previous pass shipped. The product's own
mechanism — duration-locked segments assembled into a video — IS a timeline, and the UI now says so
directly: a horizontal clip track with a real waveform, a sweeping playhead, and timecodes replaces
the prior ring-and-tick "production strip" as the page's one focal instrument. This was the user's
explicit, informed choice ("Impeccable's Pick") over the tool's own anti-rut assignment, made from a
ranked list of seven grounded candidates spanning creative-pro software, ops telemetry, print
storyboards, and physical AV signage.

The warm paper-and-ink neutral system and the single industrial-orange accent carry over unchanged
from the prior system (brand-safe per the direction contract) — this is a re-staging of the same
material world around a new signature device, not a palette or type replacement. The project's own
stylesheet still states the rejection explicitly: "not the AI-slop default (no purple-blue
gradients, no glassmorphism, no Inter)."

The whole app remains one continuous page per job (the Studio route renders both `/` and
`/jobs/:jobId`): a composer at the top, framed as opening a new project, with the clip track
directly beneath it and a REC line above the track — the visual system's job is still to make real
backend progress legible, never to fabricate liveliness. Dark mode is no longer OS-driven: it is
light-only, always, regardless of `prefers-color-scheme`; `data-theme="dark"` remains defined as a
complete, first-class token set (now covering all 17 tokens, not 9) but is an unwired future opt-in,
not a live feature.

**Key Characteristics:**
- Warm paper neutrals + one industrial accent, applied narrowly
- A horizontal clip track (waveform + sweeping playhead + timecodes) as the one focal live-progress instrument, not a row of six equal-weight widgets
- Display type (Bricolage Grotesque) for numbers and headings, mono (JetBrains Mono) for uppercase labels, timecodes, and instrument readouts, sans (Geist) for body/UI text
- Soft, low-contrast ambient shadows only — no hard offset shadows, no heavy elevation
- Real, state-driven motion and data only — waveform bars are deterministic (hashed, not random or fabricated), playhead position and timecodes are read off actual SSE event timestamps, never a timer
- Light-only by design; dark-mode tokens are complete but intentionally unwired
- One consistent inline-SVG icon system app-wide; no unicode glyphs standing in for icons

## Colors

A warm paper-and-ink neutral system carries nearly all surface and text color; the accent is a
single saturated orange reserved for the primary action, the live/REC state, and milestones.

### Primary
- **Signal Orange** (`#e8542f`, `--color-accent`): the one accent. Primary button fill, the REC
  pulsing dot and rotating caption above the clip track, the sweeping playhead and its fill on the
  track itself, accent-toned pills (milestones, highlighted dropdown items), focus border on the
  composer textarea. Paired with **Signal Orange Tint** (`#ffe9e1`, `--color-accent-tint`) as its
  low-emphasis background (accent pill fill, selected duration chip, active clip-block fill).

### Neutral
- **Paper 0** (`#fbfaf6`): page background, primary surface (cards' inner content, dialogs, dropdown menus).
- **Paper 1** (`#f3f1e9`): the "raised" surface tone — `Card`, `JobCard`, `LiveProgress` panel, `WrapReport` sit one step warmer/darker than the page.
- **Paper 2** (`#e7e4d8`): track/well backgrounds (the clip track's own rail bed, meter tracks, `Tabs` list background, neutral `Pill` fill, `Skeleton` fill).
- **Ink 900** (`#16150f`): primary text, headings, active tab text.
- **Ink 700** (`#3a382e`): secondary body text, nav-adjacent text, ghost-button text.
- **Ink 500** (`#6b6759`): tertiary text — labels, timecodes, meta rows, uppercase mono captions.
- **Ink 300** (`#a8a392`): quietest text and default borders, almost always used at reduced opacity (`/20`, `/25`, `/35`, `/40`) as a hairline divider, an unfilled waveform bar, or a dashed empty-state border rather than at full strength.

### Named Rules
**The One Accent Rule.** `--color-accent` is the only saturated color outside the signal set; it
marks exactly one primary action or one "this is live right now" state per view (submit button, the
REC dot, the sweeping playhead, an active clip block). It is never used for large fills or
backgrounds.

**The Signal-Not-Decoration Rule.** `signal-run` / `signal-ok` / `signal-warn` / `signal-bad` exist
only to report real job/status state (`StatusPill`, reconnecting banner) — they are a status
vocabulary, not a general decorative palette.

**The Tier-Is-Literal-Color Rule.** `tier-0` / `tier-1` / `tier-2` render as the literal fill color
of a segment's clip block (the top-edge bar in `SegmentCard`, the tier badge) — tier is read off the
color the same way a colorist reads a scope, not inferred from a label. (`domain/tier.ts` now
correctly emits `--color-tier-N`; this rule only holds because that binding is fixed — see Do's and
Don'ts.)

## Typography

**Display Font:** Bricolage Grotesque Variable (with `ui-sans-serif, system-ui, sans-serif` fallback)
**Body Font:** Geist Variable (with `ui-sans-serif, system-ui, sans-serif` fallback)
**Label/Mono Font:** JetBrains Mono Variable (with `ui-monospace, monospace` fallback)

**Character:** A grotesque display face carries numbers and short headings with editorial weight;
Geist runs quiet body/UI text; JetBrains Mono, always uppercase and letter-spaced, marks every
instrument label, timecode, and data readout — the mono voice is what makes the console read as a
measured broadcast instrument rather than marketing copy.

### Hierarchy
- **Display** (400, `text-2xl`–`text-3xl`, ~1.2 line-height): the composer's topic textarea, the animated stat numbers in `WrapReport`, and the rotating caption line above the clip track (`PlayfulCaption`).
- **Title** (400, `text-lg`–`text-xl`, ~1.3 line-height): page/dialog titles, `EmptyState` headline, job-card topic text, segment titles on a clip block.
- **Body** (400, `text-sm`, 1.5 line-height): form labels' surrounding copy, dropdown/menu item text, toast messages — the default UI voice.
- **Label** (500 mono, 11px/`text-xs`, 0.05em tracking, uppercase): every instrument caption — timecodes on the clip track, phase labels, the REC dot's "Rec" text, pills, duration chips, nav links.

### Named Rules
**The Mono-Caps Instrument Rule.** Any text describing a measured quantity, status, or timecode
(labels, pills, timecodes, meter captions, nav) renders in uppercase JetBrains Mono at 11px with
wide tracking, tabular-nums where numeric — never the display or body face. This is what separates
"instrument readout" from "content," and it is the rule the clip track's timecodes exist to prove.

## Layout

Single-column, centered container at `max-w-4xl` (composer/studio page) with `px-6` horizontal
padding and generous `py-16` top/bottom rhythm; the header uses the same `max-w-4xl` measure at
`py-4`. Internal spacing runs a tight, mostly 4px-stepped scale — `gap-1`/`gap-1.5`/`gap-2` for
inline clusters (pills, chip rows, waveform bars), `gap-4` for card-internal groups, `gap-5`/`gap-8`
between stacked page sections. There is no multi-column grid system in evidence; the app is a single
vertical stack of instrument sections (composer → REC line → clip track → stage ticker → clip strip
→ stage log → stats/result), consistent with the "one continuous surface" product principle —
submitting a job never navigates away, only the route param changes under the same layout.

Within the live-progress panel, the clip track is horizontally full-width and the segment strip
beneath it is a horizontal `snap-x` scroll region (fixed-width `w-40` clip blocks) rather than
wrapping — an NLE clip-bin metaphor, not a responsive card grid. `SegmentGrid` (a wrapping card
grid) still exists and is still the correct layout, but only in the finished/browse view
(`JobResult`), a deliberate distinction between browsing many completed segments and watching one
live strip fill in.

Responsive behavior observed is minimal and targeted: the clip track's phase labels collapse to
showing only the active phase below `sm` (`hidden … sm:block`) rather than a broader breakpoint
system.

## Elevation & Depth

Flat by default with two soft, low-contrast ambient shadow steps used only where a surface needs to
visually separate from the page or lift on interaction — never a structural/hard-offset shadow.

### Shadow Vocabulary
- **Shadow 1** (`0 1px 2px rgb(22 21 15/0.06), 0 0 0 1px rgb(22 21 15/0.05)`): resting elevation for `Card`, the active `Tabs` trigger, a resting clip block.
- **Shadow 2** (`0 8px 24px -8px rgb(22 21 15/0.18), 0 0 0 1px rgb(22 21 15/0.06)`): overlay/popover elevation — `Dialog` content, `DropdownMenu` content, `Tooltip`, toasts, and the hover state of `JobCard`.

### Named Rules
**The Ambient-Only Rule.** Shadows are diffuse and low-opacity in this world; a hard-offset/outlined
shadow would contradict the paper-and-ink editorial register and is not part of this system.

## Shapes

Corners are soft but not pill-like by default: `radius-sm` (6px) for compact controls (menu items,
active-tab chip), `radius-md` (10px) for buttons/cards/dialog-adjacent controls, inputs, and the
clip track's rail, `radius-lg` (16px) for `Card` and `Dialog`/`DropdownMenu` containers. Fully-rounded
(`rounded-full`) is reserved for the mono-label pill family (`Pill`, `StatusPill`, `TierBadge`,
duration chips), for meter tracks/fills, and for individual waveform bars. Borders are consistently
hairline and low-contrast, almost always `ink-300` at reduced opacity (`/20`–`/40`) rather than a
solid full-strength border; dashed borders (`EmptyState`, unassigned `TierBadge`) mark an explicitly
empty/pending state.

Icons are a single inline-SVG system (`components/icons.tsx`): one shared 16×16 viewBox, 1.75
stroke weight, round caps/joins, `currentColor` — replacing every prior unicode-glyph-as-icon
instance app-wide. No icon font, no external icon package, no emoji standing in for a control.

## Components

### Buttons
- **Shape:** `rounded-md` (10px), bordered.
- **Primary:** `bg-accent` / `text-paper-0`, transparent border; on hover gains a glow ring (`box-shadow: 0 0 0 1px accent, 0 6px 20px -6px accent`) plus a pointer-tracked radial-gradient sheen driven by CSS custom properties set from `onPointerMove` (no React re-render).
- **Secondary:** `bg-paper-0` / `text-ink-900`, `ink-300/40` border.
- **Ghost:** transparent, `text-ink-700`, `hover:bg-paper-1`.
- **Hover/Focus:** all variants lift 1px (`-translate-y-px`) and settle on active (`scale-[.985]`), transitioning over `--duration-1` (120ms) with `--ease-expo-out`. Focus now shows the app-wide `:focus-visible` ring (see below); no per-component override needed.

### Chips / Pills
- **Style:** `rounded-full`, mono 11px uppercase label text, tone-based background/text pairing (neutral/run/ok/warn/bad/accent), each tone at ~12% background opacity over its full-strength text color.
- **State:** `StatusPill` maps job status → tone directly; duration chips in `PromptComposer` use accent border+tint when selected, quiet ink border otherwise; `TierBadge` is a distinct, animated variant (flip-in on tier assignment, pulsing glow on the rare Tier 2/"Animated" result) rather than a static pill.

### Cards / Containers
- **Corner Style:** `rounded-lg` (16px).
- **Background:** `paper-1` (one step warmer than page background).
- **Shadow Strategy:** Shadow 1 at rest; `JobCard` additionally lifts to Shadow 2 + `-translate-y-0.5` on hover.
- **Border:** hairline `ink-300/25`.
- **Internal Padding:** `p-5` (20px).

### Inputs / Fields
- **Style:** the composer textarea is the only free-text input in evidence — `rounded-md`, `ink-300/30` border, `paper-0` background, set in display type (`text-2xl`) rather than body type, signaling it's the page's primary act, not a form field among many.
- **Focus:** border shifts to `accent`, plus the app-wide themed `:focus-visible` ring (`outline: 2px solid var(--color-ring)`, 2px offset) — a real gap in the prior system, now closed globally rather than per-component.

### Navigation
- Header nav is text-only: mono `text-xs` links in `ink-500`, hover to `ink-900`, no active-state underline or background observed; a secondary "New video" button anchors the right edge. Tabs (`RadixTabs`) render as a segmented control: `paper-2` track, `paper-0`/Shadow-1 active trigger. `DropdownMenu`'s highlighted item is now accent-tinted (`accent-tint` background, `accent` text) rather than flat gray, matching the One Accent Rule's "this matters right now" usage.

### Clip Track (signature component)
`ClipTrack` is the system's defining custom pattern and the direction's stated reason for being: a
horizontal broadcast-timeline rail (`bg-paper-2`) filled with a deterministic, hash-seeded waveform
(bar count keyed to real segment count, heights from a seeded pseudo-random function — never
`Math.random()` and never a stand-in for actual audio analysis) that fills with accent color as real
phase progress advances, topped by a sweeping playhead (`IconPlayhead`) that glides via a
`layoutId`-free CSS transition to the leading edge of that progress, with a pulsing accent halo
behind it. Beneath the rail, each pipeline phase gets a mono timecode read directly off the first
matching SSE transition event's timestamp (`--:--` if that phase hasn't started — never a fabricated
value) and a label that collapses to only the active phase below `sm`. It replaces the prior
"production strip" (numbered circular ticks) entirely; that component no longer exists in the
codebase.

### Clip Strip
`ClipStrip` is the live-progress counterpart of `SegmentGrid`: a horizontal `snap-x` scroll strip of
fixed-width (`w-40`) clip blocks (`SegmentCard`), with a static right-edge gradient fade signaling
more content scrolls off-screen (a deliberate cheap always-on hint, not a measured-overflow
affordance). Used only in the live view; `SegmentGrid`'s wrapping card grid remains the correct
pattern for the finished/browse view in `JobResult` — two different tasks (watching a strip fill in
live vs. browsing many completed segments), not an inconsistency.

### REC Line
`PlayfulCaption`, restyled this pass into a broadcast REC indicator: a pulsing accent dot + "Rec"
label, the real current phase name in quiet mono, and a rotating personality caption in display
type — sitting above the clip track as the panel's status headline. Past 90 seconds in one phase the
rotating copy switches to factual `LONG_WAIT_COPY` rather than continuing to joke, so playful copy
never reads as mockery during a genuinely long wait.

## Do's and Don'ts

### Do:
- **Do** use JetBrains Mono, uppercase, wide-tracked, tabular-nums, for any label describing a measured value, status, or timecode — this is the system's signature instrument voice.
- **Do** keep shadows soft and ambient (Shadow 1 / Shadow 2 only); reserve them for genuine surface separation or hover lift, not general decoration.
- **Do** redefine color tokens under identical names for dark mode rather than adding `dark:` variants — this is how the codebase achieves zero-`dark:`-class components today, even while dark mode itself stays unwired.
- **Do** drive animated state (waveform fill, playhead position, timecodes, counts, badges) from real backend data (`duration_ms`, tier assignment, SSE event timestamps), never a fabricated timer or invented percentage — this is a product-level commitment (PRODUCT.md: "Real progress, never fabricated"), not just a style preference.
- **Do** put the live progress view's segments on a horizontal clip strip/track, never a wrapping card grid — reserve the card grid for the finished/browse view, where a different task (scanning many completed items) makes it the right tool.
- **Do** use the shared `components/icons.tsx` inline-SVG set for any icon; never a unicode glyph or emoji as a stand-in control.

### Don't:
- **Don't** introduce a second saturated accent color; the One Accent Rule is load-bearing for how sparse and deliberate the orange currently reads.
- **Don't** add hard-offset or high-contrast drop shadows; nothing in the shipped system uses them and they would break the flat-paper register.
- **Don't** let the OS/browser `prefers-color-scheme` drive the palette; the app is light-only, always, by explicit decision (T37/D144) — `data-theme="dark"` is a complete token set kept for a future opt-in control, not a live feature to wire up implicitly.
- **Don't** treat repeated/duplicate phase labels in `StageTicker` as a design choice to preserve or restyle around; when they occur it is because `segmentTitle` isn't always populated on certain backend SSE events (`api/events.py`/`core/graph` territory) — a data gap to fix upstream, not a frontend pattern.
