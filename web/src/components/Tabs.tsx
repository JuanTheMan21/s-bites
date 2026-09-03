import * as RadixTabs from '@radix-ui/react-tabs'
import { classNames } from './class-names'

export interface TabOption {
  value: string
  label: string
}

interface Props {
  value: string
  onValueChange: (value: string) => void
  options: TabOption[]
}

export function Tabs({ value, onValueChange, options }: Props) {
  return (
    <RadixTabs.Root value={value} onValueChange={onValueChange}>
      <RadixTabs.List className="inline-flex gap-1 rounded-md bg-paper-2 p-1">
        {options.map((option) => (
          <RadixTabs.Trigger
            key={option.value}
            value={option.value}
            className={classNames(
              'rounded-sm px-3 py-1.5 font-sans text-sm text-ink-700 transition-colors duration-(--duration-1)',
              'data-[state=active]:bg-paper-0 data-[state=active]:text-ink-900 data-[state=active]:shadow-(--shadow-1)',
            )}
          >
            {option.label}
          </RadixTabs.Trigger>
        ))}
      </RadixTabs.List>
    </RadixTabs.Root>
  )
}
