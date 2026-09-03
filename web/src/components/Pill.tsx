import type { HTMLAttributes } from 'react'
import { classNames } from './class-names'

interface Props extends HTMLAttributes<HTMLSpanElement> {
  tone?: 'neutral' | 'run' | 'ok' | 'warn' | 'bad' | 'accent'
}

const TONE_CLASS: Record<NonNullable<Props['tone']>, string> = {
  neutral: 'bg-paper-2 text-ink-700',
  run: 'bg-signal-run/12 text-signal-run',
  ok: 'bg-signal-ok/12 text-signal-ok',
  warn: 'bg-signal-warn/12 text-signal-warn',
  bad: 'bg-signal-bad/12 text-signal-bad',
  accent: 'bg-accent-tint text-accent',
}

export function Pill({ tone = 'neutral', className, ...rest }: Props) {
  return (
    <span
      className={classNames(
        'inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 font-mono text-[11px] font-medium tracking-wide uppercase',
        TONE_CLASS[tone],
        className,
      )}
      {...rest}
    />
  )
}
