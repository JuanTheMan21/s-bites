import type { PipelinePhase } from '@/domain/stage'

/** Playful lines rotate WITHIN a phase the SSE stream has already confirmed is current -- never
 * invented progress. See PlayfulCaption.tsx for the two rules that keep this from grating: the
 * real stage label stays visible alongside these, and a phase running past 90s switches to
 * LONG_WAIT_COPY below instead of continuing to joke. */
export const PHASE_COPY: Record<PipelinePhase, string[]> = {
  outline: [
    'Reading the room…',
    'Arguing with the outline…',
    'Deciding what to cut…',
    'Finding the through-line…',
    'Resisting the urge to add a bullet list…',
    'Picking a title that isn’t boring…',
    'Deciding where the video actually starts…',
    'Cutting the second intro…',
  ],
  voice: [
    'Warming up the narrator…',
    'Taking it from the top…',
    'Doing another take…',
    'Timing the pauses…',
    'Measuring every syllable…',
    'Clearing its throat…',
    'Re-reading that sentence out loud…',
    'Getting the emphasis right…',
    'Not rushing the good part…',
  ],
  budget: [
    'Spending the frame budget…',
    'Deciding what deserves motion…',
    'Playing favourites, responsibly…',
    'Doing the math on where animation pays off…',
    'Rationing the expensive frames…',
    'Making the important parts move…',
  ],
  visuals: [
    'Sketching on the whiteboard…',
    'Auditioning diagrams…',
    'Rejecting a pie chart…',
    'Choosing a layout that isn’t a wall of text…',
    'Storyboarding, roughly…',
    'Deciding what the eye should hit first…',
    'Trying it as a diagram instead…',
  ],
  scenes: [
    'Blocking the shot…',
    'Aligning things to the grid…',
    'Nudging one pixel left…',
    'Choosing where the annotation points…',
    'Making sure nothing overlaps…',
    'Setting the pace of the reveal…',
    'Double-checking the timing lines up…',
  ],
  render: [
    'Rolling camera…',
    'Rendering the frames…',
    'Waiting on the GPU, politely…',
    "This is the slow one. It's worth it.",
    'Compositing the layers…',
    'Baking in the motion…',
    'Frame by frame, patiently…',
    'Letting the animation breathe…',
  ],
  finalize: [
    'Mixing audio…',
    'Rolling credits…',
    'Almost there — really this time.',
    'Stitching the segments together…',
    'Syncing the captions…',
    'One last pass…',
    'Checking nothing drifted out of sync…',
  ],
  unknown: ['Working…'],
}

/** Rotating, factual lines for a phase that has run past 90s (PlayfulCaption's own pin logic) --
 * still honest about the wait, just no longer joking about it. */
export const LONG_WAIT_COPY: Record<PipelinePhase, string[]> = {
  outline: [
    'Still outlining — the planning stage, before anything else can start.',
    'Still shaping the outline.',
  ],
  voice: [
    'Still recording narration — this scales with how much there is to say.',
    'Still narrating, segment by segment.',
  ],
  budget: [
    'Still budgeting motion — a short, whole-video decision, but a real one.',
    'Still deciding where the animation budget goes.',
  ],
  visuals: [
    'Still designing visuals — planning every segment’s layout at once.',
    'Still working out the visual plan.',
  ],
  scenes: [
    'Still composing scenes — laying out every segment’s content.',
    'Still building each segment’s scene.',
  ],
  render: [
    'Still rendering — genuinely the slowest step. Frame-by-frame takes time.',
    'Still rendering frames, segment by segment.',
  ],
  finalize: ['Still mixing the final cut — almost done.', 'Still stitching everything together.'],
  unknown: ['Still working…'],
}
