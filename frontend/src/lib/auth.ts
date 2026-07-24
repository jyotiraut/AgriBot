import { create } from 'zustand'
import { persist } from 'zustand/middleware'

// Admin gate matches the backend exactly (api/routes.py: current_user.email ==
// "admin@gmail.com") — the backend is the real authority (this endpoint still
// 403s for anyone else); this just decides whether to show the nav link.
export const ADMIN_EMAIL = 'admin@gmail.com'

interface AuthState {
  token: string | null
  userId: string | null
  name: string | null
  email: string | null
  setAuth: (token: string, userId: string, name: string, email: string) => void
  logout: () => void
}

export const useAuth = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      userId: null,
      name: null,
      email: null,
      setAuth: (token, userId, name, email) => set({ token, userId, name, email }),
      logout: () => set({ token: null, userId: null, name: null, email: null }),
    }),
    { name: 'krishimitra-auth' },
  ),
)

export function useIsAdmin() {
  return useAuth((s) => s.email === ADMIN_EMAIL)
}
