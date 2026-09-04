import * as RadixMenu from '@radix-ui/react-dropdown-menu'
import type { ReactNode } from 'react'
import { classNames } from './class-names'

export interface MenuItem {
  key: string
  label: string
  icon?: ReactNode
  disabled?: boolean
  disabledReason?: string
  onSelect?: () => void
  href?: string
}

export function DropdownMenu({ trigger, items }: { trigger: ReactNode; items: MenuItem[] }) {
  return (
    <RadixMenu.Root>
      <RadixMenu.Trigger asChild>{trigger}</RadixMenu.Trigger>
      <RadixMenu.Portal>
        <RadixMenu.Content
          align="end"
          sideOffset={8}
          className="z-50 min-w-48 rounded-md border border-ink-300/25 bg-paper-0 p-1 shadow-(--shadow-2)"
        >
          {items.map((item) => (
            <RadixMenu.Item
              key={item.key}
              disabled={item.disabled}
              onSelect={item.onSelect}
              asChild={Boolean(item.href) && !item.disabled}
              className={classNames(
                'flex cursor-pointer items-center gap-2 rounded-sm px-2.5 py-2 text-sm text-ink-900 transition-colors duration-(--duration-1)',
                'outline-none data-[highlighted]:bg-accent-tint',
                item.disabled && 'cursor-not-allowed text-ink-300 data-[highlighted]:bg-transparent data-[highlighted]:text-ink-300',
              )}
              title={item.disabled ? item.disabledReason : undefined}
            >
              {item.href && !item.disabled ? (
                <a href={item.href} download>
                  {item.icon}
                  {item.label}
                </a>
              ) : (
                <>
                  {item.icon}
                  {item.label}
                  {item.disabled && item.disabledReason && (
                    <span className="ml-auto text-[11px] text-ink-300">
                      {item.disabledReason}
                    </span>
                  )}
                </>
              )}
            </RadixMenu.Item>
          ))}
        </RadixMenu.Content>
      </RadixMenu.Portal>
    </RadixMenu.Root>
  )
}
