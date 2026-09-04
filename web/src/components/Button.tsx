import type { ButtonHTMLAttributes, PointerEvent as ReactPointerEvent, ReactNode } from 'react'
import { classNames } from './class-names'

type Variant = 'primary' | 'secondary' | 'ghost'

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  icon?: ReactNode
}

const VARIANT_CLASS: Record<Variant, string> = {
  primary: 'bg-accent-solid text-paper-0 border-transparent',
  secondary: 'bg-paper-0 text-ink-900 border-ink-300/40',
  ghost: 'bg-transparent text-ink-700 border-transparent hover:bg-paper-1',
}

/** The hover glow/lift/sheen lives entirely in CSS custom properties driven by pointer position
 * -- one `onPointerMove` handler, zero React re-renders, so it costs nothing on the compositor. */
function trackPointer(e: ReactPointerEvent<HTMLButtonElement>) {
  const rect = e.currentTarget.getBoundingClientRect()
  e.currentTarget.style.setProperty('--mx', `${e.clientX - rect.left}px`)
  e.currentTarget.style.setProperty('--my', `${e.clientY - rect.top}px`)
}

export function Button({ variant = 'primary', icon, className, children, ...rest }: Props) {
  return (
    <button
      onPointerMove={trackPointer}
      className={classNames(
        'group relative isolate inline-flex items-center justify-center gap-2 overflow-hidden',
        'rounded-md border px-4 py-2 font-sans text-sm font-medium',
        'transition-[transform,box-shadow] duration-(--duration-1) ease-(--ease-expo-out)',
        'hover:-translate-y-px active:translate-y-0 active:scale-[.985]',
        variant === 'primary' &&
          'hover:shadow-[0_0_0_1px_var(--color-accent),0_6px_20px_-6px_var(--color-accent)]',
        VARIANT_CLASS[variant],
        'disabled:pointer-events-none disabled:opacity-50',
        className,
      )}
      {...rest}
    >
      <span
        aria-hidden
        className="pointer-events-none absolute inset-0 -z-10 opacity-0 transition-opacity duration-(--duration-2) group-hover:opacity-100"
        style={{
          background:
            'radial-gradient(120px circle at var(--mx,50%) var(--my,50%), rgb(255 255 255 / 0.16), transparent 70%)',
        }}
      />
      {icon}
      {children}
    </button>
  )
}
