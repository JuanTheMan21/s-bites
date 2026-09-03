import type { HTMLAttributes } from 'react'
import { classNames } from './class-names'

export function Card({ className, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={classNames(
        'rounded-lg border border-ink-300/25 bg-paper-1 p-5 shadow-(--shadow-1)',
        className,
      )}
      {...rest}
    />
  )
}
