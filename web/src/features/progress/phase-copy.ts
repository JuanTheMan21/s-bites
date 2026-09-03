import type { PipelinePhase } from '@/domain/stage'

/** Playful lines rotate WITHIN a phase the SSE stream has already confirmed is current -- never
 * invented progress. See PlayfulCaption.tsx for the two rules that keep this from grating: the
 * real stage label stays visible alongside these, and a phase running past 90s pins to a factual
 * line instead of continuing to joke. */
export const PHASE_COPY: Record<PipelinePhase, string[]> = {
  outline: [
    'Reading the room…',
    'Arguing with the outline…',
    'Deciding what to cut…',
    'Finding the through-line…',
    'Resisting the urge to add a bullet list…',
  ],
  voice: [
    'Warming up the narrator…',
    'Taking it from the top…',
    'Doing another take…',
    'Timing the pauses…',
    'Measuring every syllable…',
  ],
  budget: [
    'Spending the frame budget…',
    'Deciding what deserves motion…',
    'Playing favourites, responsibly…',
  ],
  visuals: ['Sketching on the whiteboard…', 'Auditioning diagrams…', 'Rejecting a pie chart…'],
  scenes: ['Blocking the shot…', 'Aligning things to the grid…', 'Nudging one pixel left…'],
  render: [
    'Rolling camera…',
    'Rendering the frames…',
    'Waiting on the GPU, politely…',
    "This is the slow one. It's worth it.",
  ],
  finalize: ['Mixing audio…', 'Rolling credits…', 'Almost there — really this time.'],
  unknown: ['Working…'],
}
