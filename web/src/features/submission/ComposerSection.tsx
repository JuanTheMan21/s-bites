import { useState } from 'react'
import { Button } from '@/components/Button'
import { classNames } from '@/components/class-names'
import { IconPlus } from '@/components/icons'
import { PromptComposer } from './PromptComposer'

/** `collapsed=false` on `/` (the composer *is* the page). `collapsed=true` once a job exists
 * (StudioPage rendering `/jobs/:jobId`) -- the composer starts folded to a one-line trigger so it
 * never competes with a live or finished result for page-top space, but stays reachable without
 * leaving the page (the whole point of not navigating away on submit). */
export function ComposerSection({ collapsed }: { collapsed: boolean }) {
  const [expanded, setExpanded] = useState(!collapsed)

  if (collapsed && !expanded) {
    return (
      <button
        onClick={() => setExpanded(true)}
        className="inline-flex items-center gap-1.5 self-start rounded-full border border-ink-300/30 px-4 py-2 font-mono text-xs text-ink-500 transition-colors duration-(--duration-1) hover:border-accent hover:text-ink-900"
      >
        <IconPlus className="h-3 w-3" />
        New video
      </button>
    )
  }

  return (
    <div className={classNames('flex flex-col gap-5', !collapsed && 'mx-auto w-full max-w-3xl')}>
      {!collapsed && (
        <div className="flex flex-col gap-4">
          <h1 className="font-display text-5xl leading-[0.95] text-ink-900 sm:text-6xl">
            Turn a topic into an AI-narrated explainer.
          </h1>
          <p className="text-lg text-ink-500">
            Type what you want explained. AI writes the outline and narration, then builds the
            video segment by segment while you watch it come together.
          </p>
        </div>
      )}
      <PromptComposer />
      {collapsed && (
        <Button variant="ghost" onClick={() => setExpanded(false)} className="self-start">
          Collapse
        </Button>
      )}
    </div>
  )
}
