import { EmptyState } from '@/components/EmptyState'
import { Pill } from '@/components/Pill'

/** T29-T33 (RAG) don't exist on the backend yet -- this is an honest "coming soon" shell, not a
 * disabled facsimile of working upload behaviour. Filling it in later is wiring, not layout. */
export function LibraryPage() {
  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-4 px-6 py-16">
      <div className="flex items-center gap-2">
        <h1 className="font-display text-3xl text-ink-900">Document library</h1>
        <Pill tone="neutral">Coming soon</Pill>
      </div>
      <EmptyState
        title="Ground videos in your own documents"
        description="Upload a source document and generate a video that draws on it directly. This is on the roadmap -- not wired up yet."
      />
    </div>
  )
}
