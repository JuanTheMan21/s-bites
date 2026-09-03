/**
 * The eight graph node names (`api/events.py::STAGE_NODES`) collapsed to seven phases a viewer
 * understands, plus the SSE event shape (`adapters/stage-adapter.ts` parses raw JSON into this)
 * and the refresh-mid-job backfill.
 */

export type PipelinePhase =
  | 'outline'
  | 'voice'
  | 'budget'
  | 'visuals'
  | 'scenes'
  | 'render'
  | 'finalize'
  | 'unknown'

const NODE_TO_PHASE: Record<string, PipelinePhase> = {
  plan_segments: 'outline',
  synthesize_segment: 'voice',
  assign_tiers: 'budget',
  plan_visuals: 'visuals',
  author_scene: 'scenes',
  collect_scenes: 'scenes',
  render_scene: 'render',
  finalize: 'finalize',
}

export const PHASE_ORDER: PipelinePhase[] = [
  'outline',
  'voice',
  'budget',
  'visuals',
  'scenes',
  'render',
  'finalize',
]

export const PHASE_LABEL: Record<PipelinePhase, string> = {
  outline: 'Outlining',
  voice: 'Recording narration',
  budget: 'Budgeting motion',
  visuals: 'Designing visuals',
  scenes: 'Composing scenes',
  render: 'Rendering',
  finalize: 'Mixing the final cut',
  unknown: 'Working',
}

function toTitleCase(raw: string): string {
  return raw
    .split(/[_\s]+/)
    .filter(Boolean)
    .map((word) => word[0]!.toUpperCase() + word.slice(1))
    .join(' ')
}

/** A graph node this file has never heard of (T18 adding one, or any future iteration) still
 * becomes a legible step in the timeline instead of a crash or a blank row. */
export function phaseForNode(node: string): { phase: PipelinePhase; label: string } {
  const phase = NODE_TO_PHASE[node]
  if (phase) return { phase, label: PHASE_LABEL[phase] }
  return { phase: 'unknown', label: toTitleCase(node) }
}

export type StageEvent =
  | {
      kind: 'transition'
      node: string
      phase: PipelinePhase
      label: string
      edge: 'start' | 'end'
      segmentIndex?: number
      segmentTitle?: string
      at: number
    }
  | { kind: 'status'; status: 'succeeded' | 'failed'; terminal: boolean; at: number }
  | { kind: 'unknown'; raw: unknown; at: number }

interface CompletionSignal {
  durationMs: number | null
  tier: number | null
  hasScene: boolean
}

/** Backfills which phases are already complete from a job's own durable REST state -- the SSE
 * stage timeline itself always restarts empty on a fresh subscription, so this is what keeps a
 * page refresh mid-job from looking like progress was lost. */
export function deriveCompletedPhases(segments: CompletionSignal[]): Set<PipelinePhase> {
  const done = new Set<PipelinePhase>()
  if (segments.length === 0) return done
  done.add('outline')
  if (segments.every((s) => s.durationMs !== null)) done.add('voice')
  if (segments.every((s) => s.tier !== null)) {
    done.add('budget')
    done.add('visuals')
  }
  if (segments.every((s) => s.hasScene)) done.add('scenes')
  return done
}
