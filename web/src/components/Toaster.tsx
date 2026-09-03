import { AnimatePresence, m } from 'motion/react'
import { useEffect } from 'react'
import { classNames } from './class-names'
import { useToastStore } from './toast-store'

const AUTO_DISMISS_MS = 5000

function ToastRow({ id, message, tone }: { id: number; message: string; tone: 'neutral' | 'bad' }) {
  const dismiss = useToastStore((s) => s.dismiss)
  useEffect(() => {
    const timer = setTimeout(() => dismiss(id), AUTO_DISMISS_MS)
    return () => clearTimeout(timer)
  }, [id, dismiss])

  return (
    <m.div
      layout
      initial={{ opacity: 0, y: 12, scale: 0.96 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, x: 24 }}
      transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
      className={classNames(
        'rounded-md border px-4 py-3 font-sans text-sm shadow-(--shadow-2)',
        tone === 'bad'
          ? 'border-signal-bad/30 bg-paper-0 text-signal-bad'
          : 'border-ink-300/25 bg-paper-0 text-ink-900',
      )}
    >
      {message}
    </m.div>
  )
}

export function Toaster() {
  const toasts = useToastStore((s) => s.toasts)
  return (
    <div className="fixed right-4 bottom-4 z-[100] flex flex-col gap-2">
      <AnimatePresence>
        {toasts.map((t) => (
          <ToastRow key={t.id} {...t} />
        ))}
      </AnimatePresence>
    </div>
  )
}
