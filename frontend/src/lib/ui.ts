import { create } from 'zustand'
import { persist } from 'zustand/middleware'

type Theme = 'light' | 'dark'

interface UiState {
  theme: Theme
  chatSidebarOpen: boolean
  toggleTheme: () => void
  setChatSidebarOpen: (open: boolean) => void
}

const prefersDark =
  typeof window !== 'undefined' && window.matchMedia?.('(prefers-color-scheme: dark)').matches

export const useUi = create<UiState>()(
  persist(
    (set, get) => ({
      theme: prefersDark ? 'dark' : 'light',
      chatSidebarOpen: true,
      toggleTheme: () => set({ theme: get().theme === 'dark' ? 'light' : 'dark' }),
      setChatSidebarOpen: (open) => set({ chatSidebarOpen: open }),
    }),
    { name: 'krishimitra-ui' },
  ),
)

/** Keep <html class="dark"> in sync with the store, including on first paint. */
export function applyTheme(theme: Theme) {
  document.documentElement.classList.toggle('dark', theme === 'dark')
}
