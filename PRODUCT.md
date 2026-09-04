# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Two audiences, roughly equal weight, both entering the same one-page studio:

- **L&D / corporate trainers**, producing onboarding, compliance, or upskilling content for their
  organization, ending with a real SCORM 1.2 package they import into their LMS.
- **Individual self-directed learners**, typing a topic they personally want explained and
  watching the resulting video themselves. SCORM export is invisible to this audience, not a
  distraction.

The UI does not branch or ask which persona a visitor is — both paths look identical until the
"Download" menu, where SCORM either matters or goes unused.

## Product Purpose

Turn a typed topic ("teach me about SQL injection") into a narrated ~7-minute explainer video,
end to end, with no manual editing step: an LLM writes the outline and script, TTS narrates it,
HTML/HyperFrames renders the visuals, ffmpeg muxes the result. Success is a finished MP4 (plus an
importable SCORM package) that a visitor never had to touch a timeline or an editor to get.

## Positioning

**Real narration-locked timing, not an LLM's guess.** TTS runs before scene authoring and every
visual is timed to the *measured* audio duration (`duration_ms`), never an estimate — this is the
#1 source of A/V drift in comparable AI-video tools, and it is structurally prevented here
(`scene_author` takes `duration_ms` as a required parameter, so calling it early is a type error).
A competitor generating visuals off a predicted script length cannot truthfully make the same
claim.

## Operating Context

A visitor lands on one page, types a topic, picks a target duration (3/7/10 min), and watches the
same page turn into a live production view — an outline forms, narration records, motion gets
budgeted per segment, visuals render tier-by-tier, and a final cut gets composed — without ever
navigating away or losing the composer. When it finishes: a playable video, a per-segment scene
inspector, and downloads for the MP4, subtitles, and (when relevant) a SCORM package an LMS can
import directly.

## Capabilities and Constraints

- Real backend today: Azure OpenAI (outline/script), Azure Speech (narration), local HyperFrames
  render (Playwright + ffmpeg), Azure Blob (artifacts). `RUNTIME_ENV=azure` is this machine's
  active configuration.
- Three render tiers per segment (Tier 0 static, Tier 1 reveal, Tier 2 fully animated), assigned by
  a frame budget, not a flat setting — visible to the visitor as a live "tier assignment" meter and
  a color-coded badge per segment.
- SCORM 1.2 export is real, not a stub: a genuine `imsmanifest.xml` + launch page running SCORM
  1.2's own API-discovery/`LMSInitialize`/`LMSSetValue`/`LMSFinish` sequence, zipped with the video
  and subtitles.
- No authentication/user model exists yet — every milestone/achievement shown in the UI is derived
  purely from `GET /jobs`, not a per-user server record.
- The frontend is structurally insulated from the visual-authoring internals (block types, layouts,
  Jinja templates) by a generic, data-driven scene renderer — a new block type never requires a
  frontend change.

## Brand Commitments

Name: **skill-bites** (confirmed against the project's own Azure resource names, e.g.
`skill-bites.cognitiveservices.azure.com`). Header wordmark and browser tab title already carry
this; do not revert it in future visual work.

## Evidence on Hand

Two real Azure end-to-end renders exist as proof the pipeline works (T24-T28+T36 checkpoint), one
verified by downloading and unzipping a real SCORM package (`imsmanifest.xml` + `launch.html` +
`video.mp4` all present). No customer testimonials, case studies, pricing, or press exist — future
work must not fabricate any.

## Product Principles

1. **Measured, not guessed.** Every timing-sensitive decision (scene duration, A/V sync) derives
   from real measured data, never an LLM estimate — this is the product's core credibility claim.
2. **One continuous surface.** The composer and the live/finished result share one page and one
   URL pattern; submitting never navigates the visitor away from what they're watching happen.
3. **Real progress, never fabricated.** Loading-state motion, playful copy, and stats are always a
   function of genuine backend state — no invented percentages, no points/XP/leaderboard theatre.
4. **Enterprise-credible without being sterile.** The product must read as something a professional
   UI/UX team shipped, not a generic AI-tool template — polished and *alive* (real hover/motion),
   not corporate-flat.
5. **The visual layer is separable from the authoring internals.** Scene/block/layout changes must
   never force a frontend rewrite, and vice versa.

## Accessibility & Inclusion

No formal standard has been set as a hard requirement yet. Known gap, flagged during T37 planning:
no focus-visible ring exists anywhere in the current UI — closing this is in scope for T37.
