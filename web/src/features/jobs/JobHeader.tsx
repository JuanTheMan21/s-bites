import { useState } from 'react'
import { StatusPill } from '@/components/StatusPill'
import type { JobView } from '@/domain/job'

export function JobHeader({ job }: { job: JobView }) {
  const [copied, setCopied] = useState(false)

  async function copyLink() {
    await navigator.clipboard.writeText(window.location.href)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  return (
    <div className="flex flex-col gap-2.5 border-b border-ink-300/20 pb-6">
      <div className="flex items-start justify-between gap-4">
        <p className="font-display text-3xl text-ink-900">{job.topic}</p>
        <StatusPill status={job.status} />
      </div>
      <div className="flex items-center gap-3 font-mono text-xs text-ink-500">
        <span>{job.jobId}</span>
        <button
          onClick={copyLink}
          className="underline decoration-dotted transition-[color,text-decoration-color] duration-(--duration-1) hover:text-ink-900 hover:decoration-accent"
        >
          {copied ? 'Copied' : 'Copy link'}
        </button>
      </div>
    </div>
  )
}
