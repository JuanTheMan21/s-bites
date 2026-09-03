import { m } from 'motion/react'
import { Link } from 'react-router-dom'
import { StatusPill } from '@/components/StatusPill'
import type { JobView } from '@/domain/job'

function relativeTime(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime()
  const minutes = Math.round(diffMs / 60_000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.round(hours / 24)}d ago`
}

export function JobCard({ job }: { job: JobView }) {
  return (
    <m.div
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.28, ease: [0.16, 1, 0.3, 1] }}
    >
      <Link
        to={`/jobs/${job.jobId}`}
        className="group flex items-center justify-between gap-4 rounded-lg border border-ink-300/25 bg-paper-1 px-5 py-4 transition-[transform,box-shadow] duration-(--duration-1) ease-(--ease-expo-out) hover:-translate-y-0.5 hover:shadow-(--shadow-2)"
      >
        <div className="flex min-w-0 flex-col gap-1">
          <p className="truncate font-display text-lg text-ink-900">{job.topic}</p>
          <p className="font-mono text-[11px] text-ink-500">
            {job.segments.length || '—'} segments · {relativeTime(job.createdAt)}
          </p>
        </div>
        <StatusPill status={job.status} />
      </Link>
    </m.div>
  )
}
