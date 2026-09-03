import type { JobStatus } from '@/domain/job'
import { Pill } from './Pill'

const STATUS: Record<JobStatus, { label: string; tone: 'neutral' | 'run' | 'ok' | 'bad' }> = {
  queued: { label: 'Queued', tone: 'neutral' },
  running: { label: 'Running', tone: 'run' },
  succeeded: { label: 'Succeeded', tone: 'ok' },
  failed: { label: 'Failed', tone: 'bad' },
}

export function StatusPill({ status }: { status: JobStatus }) {
  const { label, tone } = STATUS[status]
  return <Pill tone={tone}>{label}</Pill>
}
