import type { HTMLAttributes } from 'react'
import { classNames } from './class-names'

export function Skeleton({ className, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={classNames('animate-pulse rounded-md bg-paper-2', className)}
      aria-hidden
      {...rest}
    />
  )
}
