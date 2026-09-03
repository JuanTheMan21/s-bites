import { useState } from 'react'
import type { StageEvent } from '@/domain/stage'

function describeEvent(event: StageEvent): string {
  if (event.kind === 'transition') {
    const segment = event.segmentIndex !== undefined ? ` #${event.segmentIndex}` : ''
    return `${event.node}${segment} ${event.edge}`
  }
  if (event.kind === 'status') {
    return `job_status=${event.status} terminal=${event.terminal}`
  }
  return 'unrecognised event'
}

export function StageLog({ events }: { events: StageEvent[] }) {
  const [open, setOpen] = useState(false)
  if (events.length === 0) return null

  return (
    <div className="rounded-md border border-ink-300/25">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between px-3 py-2 font-mono text-xs text-ink-500 hover:text-ink-900"
      >
        <span>Stage log ({events.length})</span>
        <span>{open ? '−' : '+'}</span>
      </button>
      {open && (
        <div className="max-h-48 overflow-y-auto border-t border-ink-300/25 px-3 py-2 font-mono text-[11px] text-ink-700">
          {events.map((event, i) => (
            <div key={i} className="py-0.5">
              {describeEvent(event)}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
