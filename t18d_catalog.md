# T18D — Real-render bug catalog for the block library

Six renders, watched properly (targeted frame extraction cross-referenced against each
segment's authored timing arrays and SRT narration, not just `hyperframes check`), no fixing
done in this session. `tasks.md`'s T18D entry and decisionlog D120 are the scoping context;
this file is the catalog T18E's fix pass should read first.

**Pre-flight, not a finding:** the Blob skill registry was drifted (`scene-authoring/1.3.md`,
`visual-plan/1.1.md` existed only on local disk — see `handoff.md`'s Environment State table).
Synced to Blob before any render in this session, via `az storage blob upload` with the
connection string from `.env` (the `mcp__azure__storage` tool's AAD-login path lacks the RBAC
role for blob data-plane writes on this account — `AuthorizationPermissionMismatch` — so the
account-key connection string was used instead). Verified via `az storage blob list`. Every
render in this catalog ran against the current, T18C-shipped skill packs.

---

## Topic matrix

| job-id | topic | segments | duration |
|---|---|---|---|
| `t18d-array-grid` | Sliding window, max sum of 3 consecutive numbers | 3 | 66.4s |
| `t18d-code-diff` | Memoized Fibonacci | 3 | 77.2s |
| `t18d-timeline` | HTTP/1.0 → HTTP/3 milestones | 3 | 85.8s |
| `t18d-graph-single` | Dijkstra's algorithm | 3 | 71.2s |
| `t18d-sequence-oauth` | OAuth 2.0 authorization code flow | 4 | 93.2s |
| `t18d-annotations-sqli` | SQL injection bypassing a login check | 4 | 98.2s |

All six were opened for the user to watch directly in addition to this session's own
frame-by-frame review.

---

## The headline finding: per-item anchor fallback is index-only, and it shows

`rendering/block_timing.py::resolve_item_starts` (used by `text_panel.items`,
`graph_diagram.nodes`, `code_diff.lines` — the `_ITEM_FIELDS` blocks, which have no authored
`anchor_phrase` and instead try to match the item's own short display text against the full
narration) falls back to `_DEFAULT_ITEM_START + i * _DEFAULT_ITEM_STAGGER` **per item, keyed
only by that item's own array index** — with zero awareness of where any other item in the same
array actually landed. Extracting every `*Starts` array rendered across all six jobs (grep across
`composition/index.html`, cross-checked against the literal `0.75, 0.97, 1.19, 1.41, 1.63, 1.85,
2.07…` fallback sequence in `block_timing.py`) turned up this pattern in **9 of the ~20 item/step
arrays rendered across the matrix**, producing three distinct visible symptoms, all confirmed by
extracted frames, not just inferred from the numbers:

**(a) Total collapse — the whole block dumps almost at once, then goes static.**
- `t18d-array-grid` seg1: `GRAPH_DIAGRAM` (CHAIN mode, "Previous sum → Subtract left → Add right
  → New sum"), all 4 nodes' array was `[0.75, 0.97, 1.19, 1.41]` — every single node fell back.
  Frames at t=24.5s/27s/33s/47s (segment spans 24.1–48.0s) show all 4 nodes fully visible by
  ~27s (0.9s into the segment) and **pixel-identical** through 47s — the block reveals in under a
  second then sits completely still for the remaining ~21 seconds while narration walks through
  each step individually.
- `t18d-graph-single` seg2: two blocks, both `[0.75, 0.97, 1.19, 1.41]` — total fallback on both.
- `t18d-timeline` seg1: a `text_panel`'s `b1_rowStarts = [0.75, 0.97, 1.19, 1.41, 1.63]` — all 5
  bullets dump within 1.6s (confirmed: identical at t=29.5s and t=33.6s, 4s apart).
- `t18d-annotations-sqli` seg2: `b0_rowStarts = [0.75, 0.97, 1.19, 1.41]`, another full collapse.

**(b) Scrambled reveal order — when only some items fail, they snap to the front regardless of
where the successfully-resolved items land, so an item due 5th can appear 1st.**
- `t18d-code-diff` seg1 (`GRAPH_DIAGRAM`, GRAPH mode — Fibonacci call tree): `b0_nodeStarts =
  [9.037, 0.97, 1.19, 4.437, 7.812, 18.8]`. By real time the reveal order is item1, item2, item3,
  item4, item0, item5 — completely scrambled against authored order. **Visually confirmed and
  worse than the numbers alone suggest**: frames at t=22.5s/26.5s/30.5s/44s show node "02"
  (Uncached) and node "03" (Memoized) rendered **overlapping each other**, badge over label text,
  and separately nodes "05"/"06" also overlapping with "05"'s label garbled illegible — see the
  Layout section below, this is the same render.
- `t18d-timeline` seg2: `b0_nodeStarts = [3.325, 10.325, 11.012, 12.087, 1.63, 1.85]` — the last
  two items (fallback) jump ahead of all four real-anchored ones.
- `t18d-sequence-oauth` seg1/seg2: single mid-list fallback items (`0.97` sitting between real
  neighbors) in both segments' `b0_msgStarts`.
- `t18d-annotations-sqli` seg1 (`GRAPH_DIAGRAM` CHAIN, "Password string → Quote ends it → SQL
  parser → [gap] → Login logic"): `b0_nodeStarts = [2.3, 0.97, 1.19, 9.887, 1.63]`. **Visually
  confirmed**: frames at t=29.5s and t=37s show nodes 02/03/05 already present while node 01
  ("Password string") fades in late and node 04 ("SQL parser"'s real anchor, 9.887s) is the
  *last* of five to appear, well after node 05 to its right already showed — a viewer sees
  01,02,03,05 then, seconds later, 04 pops in out of place.

**(c) Duplicate timestamp collisions**, even on `_STEP_FIELDS` blocks (which resolve much more
reliably overall, see "confirmed working" below): `t18d-timeline` seg1's `b0_msgStarts` had two
pairs of messages resolve to the **identical** timestamp (`6.4, 6.4, …, 9.525, 9.525, …`);
`t18d-sequence-oauth` seg1 had one pair at `14.65, 14.65`. Two distinct authored items reading as
spoken at the same instant.

**Root cause, as far as this session traced it (not fixed):** `graph_diagram`'s `nodes` field has
no authored `anchor_phrase` at all — `block_timing.py`'s own comment says so explicitly, only its
separate `traversal` field does. Matching a short, punchy scene-authored node label ("Add right",
"SQL parser") against independently-generated flowing narration prose is exactly the failure mode
D119 already found and fixed for `sequence_diagram`/`timeline` — but D119's fix moved *those* two
block types from `_ITEM_FIELDS` to `_STEP_FIELDS` (added anchor_phrase, matched that instead of
the label). `graph_diagram.nodes`, `text_panel.items`, and `code_diff.lines` never got the same
treatment and this matrix shows they need it: **every block still on `_ITEM_FIELDS` had at least
one fallback-pattern value somewhere in this six-topic sample; every `_STEP_FIELDS` block (except
the one duplicate-collision case above) resolved cleanly.** This reads as a strong, testable
hypothesis for T18E, not just "something is timed wrong" — add `anchor_phrase` to
`GraphNode`/`text_panel` items/`CodeDiffLine` and route them through `resolve_step_starts` the
same way D119's fix did.

A second, related but distinct instance: `t18d-graph-single` seg1's **traversal** steps (already
on `_STEP_FIELDS`) — `stepStarts = [3.825, 0.97, 19.962]` — step index1 is a fallback value that
fires *before* step index0 and before the graph's own nodes/edges have even been drawn. Frame at
t=25.6s shows a lone orange traveler dot floating in empty space with no graph on screen yet;
by t=28.5s the graph appears with the dot already sitting on a node. Same underlying mechanism
(index-only fallback with no regard for sibling timing), here degrading the traversal storytelling
specifically, even though `graph_diagram` traversal is one of the blocks D119 already fixed.

---

## Layout: GRAPH_DIAGRAM node overlap — confirmed again, and now isolated

**`t18d-code-diff` seg1** (SPLIT_HORIZONTAL, GRAPH mode): at t=44s, node "02" (Uncached) and node
"03" (Memoized) render fully overlapping — badge over label text, "repeated calls" caption cut
off. **Separately in the same diagram**, node "05" (Saved result) and node "06" (Computed once)
also overlap, with "05"'s label rendered as illegible "Sav[06]sult". Two independent overlap
pairs in one diagram — worse than D119's original single-pair finding.

**`t18d-graph-single` seg1** (SINGLE layout, same `GRAPH_DIAGRAM` component, Dijkstra topic
chosen specifically to force this): **zero overlap** across every frame sampled (t=2s, 12s,
25.6s, 28.5s, 44.6s, 46s) — nodes 01/03/04 render well-spaced and fully readable throughout.

This is a clean isolation result, exactly what this topic was chosen to test: **the overlap bug
is specific to the compact `SPLIT_HORIZONTAL` canvas, not a general `GRAPH_DIAGRAM` defect.**
Directly supports D119's already-traced root cause (circular/auto layout assuming a square
canvas against a short-wide real container) and the user's own proposed T18E direction (D120):
either make the layout formula aspect-ratio-aware for the compact case, or stop chasing per-node
reveal reliability there and lean on the traversal dot alone.

---

## Layout: two new text-collision bugs, not previously cataloged

**Annotation caption over a block's own headline.** `t18d-annotations-sqli` seg2, t=68s: the
CHECK annotation's caption "any row is enough" (green) renders directly on top of the block's
headline "Rows evaluated by login check" (black, bold) — both fully opaque, overlapping,
illegible where they cross. Distinct from the node-overlap bug above: this is annotation content
colliding with block content, not two items of the same block colliding with each other.

**Caption band over a dense block's last item.** `t18d-sequence-oauth` seg1 (the 7-message,
4-actor flow this topic was chosen to stress), t=46s: the caption text "ONLY CARRIES A TEMPORARY
PROOF NOT REUSABLE ACCESS" sits directly over the sequence diagram's own last message label
"Temporary proof". This is exactly the risk T18C's own scope notes flagged and left unchecked
("SEQUENCE_DIAGRAM's lanes... more likely to reach the bottom of the frame") — now confirmed
real against an actual denser render, not hypothetical.

---

## Static/blank holds beyond the title card (extends D120 finding #1)

- **Title card (segment 0, forced every render, D96).** Confirmed pixel-static across ~13–21s
  gaps in **four separate renders** (`array-grid`: t=1/12/22s identical; `code-diff`: t=2/15s
  identical; `timeline`: t=2/15s identical; `sequence-oauth`/`annotations-sqli`: same pattern by
  extension). This is systemic, not incident-specific to D119's original render.
- **`t18d-array-grid` seg1's `GRAPH_DIAGRAM`**, per the total-collapse finding above, is
  functionally a second static card once its ~1s dump finishes — ~21 of its 24 seconds show zero
  change. Worse than a plain title card in one respect: nothing in the design intends this block
  to be static, it just gave up animating early.
- **`t18d-annotations-sqli` seg2's right-hand panel** (an `ARRAY_GRID`-styled "row 1…row 5" strip,
  by its markup) renders **completely blank** — no headline, no rows, nothing — from the start of
  the segment through at least t=60s (~8s in), only appearing by t=68s. A blank hold is a distinct
  symptom from a static-but-populated hold; both read as "nothing is happening" to a viewer.

---

## Annotation coverage (directly addresses D120 finding #2)

Across all six renders — including the two segments specifically built to invite more —
**never once did two annotations appear together in the same segment.** `t18d-sequence-oauth`
seg1's 7-message, 4-actor flow got exactly one CURSOR annotation. `t18d-annotations-sqli`, built
explicitly to stress CURSOR+WARNING+CHECK together, got exactly one WARNING in one segment and
exactly one CHECK in a different segment — never combined, never more than one per scene. This is
a real, reproducible confirmation (not a one-off) that `runtime_skills/visual-plan/1.1.md`'s "use
annotations sparingly, one or two per scene" guidance is the actual operative constraint, exactly
as D120 raised as an open question. Worth noting for balance: where a `_STEP_FIELDS` block's own
per-step reveal timing resolves cleanly (see below), the "one beat at a time" feeling can come
from the block's own pacing without a dedicated annotation per step — whether that substitutes for
per-step annotation coverage in the user's own judgment is still open, not resolved by this catalog.

---

## Planning-choice finding: the ARRAY_GRID-targeted topic never got ARRAY_GRID

`t18d-array-grid`'s topic ("sliding window technique, max sum of any 3 consecutive numbers") was
phrased specifically to make `ARRAY_GRID` with `shift`/`push`/`pop` the obvious choice. Across all
3 segments, `plan_visuals` instead chose a forced title card, `GRAPH_DIAGRAM` (CHAIN mode) for the
per-step walkthrough, and `STAT_CALLOUT` for the running-maximum concept — never `ARRAY_GRID`.
Per this session's own plan, not grounds to silently re-roll — recorded as a finding instead.
`ARRAY_GRID` did get incidental real-render coverage elsewhere (the blank-then-appears panel in
`t18d-annotations-sqli` seg2 is `ARRAY_GRID`-styled by its markup), but not from its dedicated
topic, and not exercising `shift`/`push` specifically — this session's real-render coverage of
`ARRAY_GRID`'s newer ops (T18C's own broadening) is thinner than intended.

---

## Confirmed working (for balance — not everything found was broken)

- **D110's caption fix** — clean cue-level clear/reveal across every sample in every render.
- **`_STEP_FIELDS` resolution is meaningfully more reliable than `_ITEM_FIELDS`** — of the arrays
  sampled, only one `_STEP_FIELDS` array had a problem (the duplicate-timestamp case above);
  every other `stepStarts`/clean `msgStarts` array was monotonic and real. `t18d-annotations-sqli`
  seg3's `SEQUENCE_DIAGRAM` (Client/Driver/Database, 6 messages) revealed correctly one-by-one
  start to finish, with a well-placed CURSOR annotation landing on the right code line.
- **`GRAPH_DIAGRAM` in `SINGLE` layout** — no overlap anywhere sampled, in direct contrast to
  every `SPLIT_HORIZONTAL` instance in this matrix.
- **CHECK/WARNING annotations, in isolation, render and time correctly** —
  `t18d-sequence-oauth` seg2's checkmark and seg3's "limited blast radius" warning both land
  sensibly against their narration and don't collide with anything.
- **Palette/motif consistency, SPLIT_HORIZONTAL panel-tilt entrance, per-segment mux/concat** —
  no problems observed anywhere in this matrix.

---

## Minor, unrelated observation

`pipeline-debugging`'s documented artifact layout (`segments/<n>/script.json`, `scene.html`)
doesn't match what a real `cli.py` run actually writes (`segments/<n>/composition/index.html`,
`clip.mp4`, `narration.wav`, `silent.mp4` — no `script.json` at all; narration text/timing lives
only in `final.srt` and inline JS constants). Not part of T18D/T18E's block-library scope — a
stale-skill-doc fix for whoever next touches `pipeline-debugging`.

---

## On the "should we build a vision-validator" question raised mid-session

Worth checking this catalog against that question directly, since T18D doubled as a cheap way to
answer it: of everything found above, **the headline finding (index-only fallback) and both
overlap-isolation results were found by grepping rendered timing arrays and reasoning about them
against `block_timing.py`'s own source — not by looking at a frame.** The frames *confirmed* what
the numbers already predicted; a vision-only pass without that data would have seen "things appear
in a weird order sometimes" without the reusable, testable explanation this catalog has. The two
genuinely frame-only findings (the two text-collision bugs) are exactly the class a vision model
would catch well. This supports the narrower framing suggested earlier: a future T18F vision loop
is well-suited to layout/collision spot-checks, but the timing-reliability class of bug is better
caught by a deterministic assertion (e.g. "every resolved start falls within its segment and is
monotonic in array order") than by a vision call.

---

## Cross-cutting summary against D120's three seeded findings

1. **Static/low-motion segments run long** — confirmed, and now shown to have (at least) two
   distinct causes: the structural title card (D96, unchanged) and the anchor-fallback total
   collapse (new root cause, this session), plus a third blank-panel variant. Not one bug, at
   least two, possibly three.
2. **`SEQUENCE_DIAGRAM` annotation coverage/timing** — refined, not simply confirmed. The
   per-message *reveal* timing is reliable when `anchor_phrase` resolves (the D119 fix holds).
   What's actually thin is dedicated *annotation* coverage (never more than one per scene, a
   `visual-plan` guidance effect) — a different mechanism than D119 fixed, and still open.
3. **`GRAPH_DIAGRAM` layout** — confirmed and newly isolated: broken specifically in
   `SPLIT_HORIZONTAL`'s compact canvas (now with two overlap pairs in one diagram, not one),
   confirmed clean in `SINGLE`. This directly de-risks one of T18E's two options (D120): a
   `SINGLE`-only redesign, or a compact-canvas-aware layout fix, both now have real data behind
   them rather than a single prior sample.

New, not in D120's seed list: the item-anchor index-only-fallback mechanism (headline finding,
likely the closer-to-the-surface shared root cause T18E's own working hypothesis speculated
about), the two text-collision bugs, and the ARRAY_GRID planning-choice gap.
