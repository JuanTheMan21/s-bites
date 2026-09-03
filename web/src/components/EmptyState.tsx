import type { ReactNode } from 'react'

interface Props {
  title: string
  description?: string
  action?: ReactNode
  icon?: ReactNode
}

export function EmptyState({ title, description, action, icon }: Props) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed border-ink-300/40 px-6 py-16 text-center">
      {icon && <div className="text-ink-500">{icon}</div>}
      <p className="font-display text-xl text-ink-900">{title}</p>
      {description && <p className="max-w-sm text-sm text-ink-500">{description}</p>}
      {action}
    </div>
  )
}
