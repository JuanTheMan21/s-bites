import { useLayoutEffect } from 'react'
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

type Theme = 'light' | 'dark'

interface ThemeState {
  theme: Theme
  toggle: () => void
}

/** Explicit opt-in only -- the app never derives this from `prefers-color-scheme` (T37/D144: no
 * forced dark theme). Default is `light`; a visitor who never touches the toggle stays light
 * regardless of their OS setting. `index.css`'s `:root[data-theme="dark"]` block already defines
 * every token this needs -- this store's only job is deciding which one applies and persisting
 * that choice, applied via `useApplyTheme` below since Zustand's `persist` writes to state, not
 * the DOM. */
export const useThemeStore = create<ThemeState>()(
  persist(
    (set) => ({
      theme: 'light',
      toggle: () => set((state) => ({ theme: state.theme === 'light' ? 'dark' : 'light' })),
    }),
    { name: 's-bites-theme' },
  ),
)

/** Applies the persisted choice to the DOM. `index.css` only ever reads `data-theme` on
 * `:root` -- no component below this needs to know the theme exists. `useLayoutEffect`, not
 * `useEffect`: the persisted value is already correct by the time this runs (Zustand's `persist`
 * rehydrates synchronously from `localStorage`), but a plain `useEffect` still fires after the
 * browser's first paint -- a returning dark-mode visitor would see one frame of light tokens on
 * every load. Running before paint closes that gap. */
export function useApplyTheme(): void {
  const theme = useThemeStore((s) => s.theme)
  useLayoutEffect(() => {
    document.documentElement.dataset.theme = theme
  }, [theme])
}
