import { useState } from 'react'
import { Button } from '@/components/Button'
import { classNames } from '@/components/class-names'
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
        className="self-start rounded-full border border-ink-300/30 px-4 py-2 font-mono text-xs text-ink-500 transition-colors duration-(--duration-1) hover:border-accent hover:text-accent"
      >
        + New video
      </button>
    )
  }

  return (
    <div className={classNames('flex flex-col gap-4', !collapsed && 'mx-auto w-full max-w-2xl')}>
      {!collapsed && (
        <div className="flex flex-col gap-3">
          <h1 className="font-display text-4xl leading-[0.95] text-ink-900 sm:text-5xl">
            Turn a topic into a narrated explainer.
          </h1>
          <p className="text-ink-500">
            Type what you want explained. We'll outline it, narrate it, and render it while you
            watch.
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
