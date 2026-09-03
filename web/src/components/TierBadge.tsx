import { AnimatePresence, m } from 'motion/react'
import { describeTier } from '@/domain/tier'
import { classNames } from './class-names'

/** The tier badge is the gamified surface T26 asks for: a segment starts with no badge and
 * *earns* one with a flip the moment a refetch shows its assigned tier. Tier 2 (ANIMATED) is the
 * rare, expensive one and gets a shimmer -- "which of my segments earned animation" becomes the
 * thing a viewer watches for, which is the whole point of making tier assignment legible. */
export function TierBadge({ tier }: { tier: number | null }) {
  const descriptor = describeTier(tier)

  return (
    <AnimatePresence mode="wait">
      {descriptor ? (
        <m.span
          key={tier}
          initial={{ rotateX: -90, opacity: 0 }}
          animate={{ rotateX: 0, opacity: 1 }}
          transition={{ duration: 0.32, ease: [0.16, 1, 0.3, 1] }}
          style={{ transformPerspective: 400 }}
          className={classNames(
            'relative inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 font-mono text-[11px] font-medium tracking-wide uppercase',
            'text-paper-0',
          )}
        >
          <span
            aria-hidden
            className="absolute inset-0 rounded-full"
            style={{ background: `var(${descriptor.colorVar})` }}
          />
          {tier === 2 && (
            <span
              aria-hidden
              className="absolute inset-0 -z-0 animate-pulse rounded-full opacity-40"
              style={{ boxShadow: `0 0 12px 2px var(${descriptor.colorVar})` }}
            />
          )}
          <span className="relative z-10">{descriptor.label}</span>
        </m.span>
      ) : (
        <span className="inline-flex items-center rounded-full border border-dashed border-ink-300/40 px-2.5 py-1 font-mono text-[11px] text-ink-500 uppercase">
          Unassigned
        </span>
      )}
    </AnimatePresence>
  )
}
