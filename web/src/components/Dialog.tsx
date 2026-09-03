import * as RadixDialog from '@radix-ui/react-dialog'
import { m } from 'motion/react'
import type { ReactNode } from 'react'

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  children: ReactNode
}

export function Dialog({ open, onOpenChange, title, children }: Props) {
  return (
    <RadixDialog.Root open={open} onOpenChange={onOpenChange}>
      <RadixDialog.Portal>
        <RadixDialog.Overlay asChild>
          <m.div
            className="fixed inset-0 z-40 bg-ink-900/40"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          />
        </RadixDialog.Overlay>
        <RadixDialog.Content asChild aria-describedby={undefined}>
          <m.div
            initial={{ opacity: 0, y: 12, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 12, scale: 0.98 }}
            transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
            className="fixed top-1/2 left-1/2 z-50 max-h-[85vh] w-[min(720px,92vw)] -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-lg border border-ink-300/25 bg-paper-0 p-6 shadow-(--shadow-2)"
          >
            <div className="mb-4 flex items-center justify-between">
              <RadixDialog.Title className="font-display text-xl text-ink-900">
                {title}
              </RadixDialog.Title>
              <RadixDialog.Close className="rounded-md px-2 py-1 text-ink-500 hover:bg-paper-1">
                Close
              </RadixDialog.Close>
            </div>
            {children}
          </m.div>
        </RadixDialog.Content>
      </RadixDialog.Portal>
    </RadixDialog.Root>
  )
}
