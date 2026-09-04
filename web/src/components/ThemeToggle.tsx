import { IconMoon, IconSun } from './icons'
import { useThemeStore } from './theme-store'

export function ThemeToggle() {
  const theme = useThemeStore((s) => s.theme)
  const toggle = useThemeStore((s) => s.toggle)
  const isDark = theme === 'dark'

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
      title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
      className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-ink-300/30 text-ink-500 transition-colors duration-(--duration-1) hover:border-accent hover:text-accent-ink"
    >
      {isDark ? <IconSun /> : <IconMoon />}
    </button>
  )
}
