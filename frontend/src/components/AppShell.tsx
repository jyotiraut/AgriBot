import type { ReactNode } from 'react'
import { Link, useNavigate, useRouterState } from '@tanstack/react-router'
import { useAuth, useIsAdmin } from '@/lib/auth'
import { ThemeToggle } from '@/components/ThemeToggle'

const NAV_ITEMS = [
  { to: '/market', label: 'Market Analysis', icon: LeafIcon },
  { to: '/chat', label: 'Chat with KrishiMitra', icon: ChatIcon },
] as const

export function AppShell({ children }: { children: ReactNode }) {
  const name = useAuth((s) => s.name)
  const logout = useAuth((s) => s.logout)
  const isAdmin = useIsAdmin()
  const navigate = useNavigate()
  const pathname = useRouterState({ select: (s) => s.location.pathname })

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-paper">
      <aside className="flex w-60 shrink-0 flex-col border-r border-hairline bg-paper-raised">
        <div className="flex items-center gap-2 border-b border-hairline px-5 py-5">
          <span className="text-xl">🌾</span>
          <span className="font-display text-lg font-semibold text-moss-700">KrishiMitra</span>
        </div>

        <nav className="flex flex-1 flex-col gap-1 p-3">
          {NAV_ITEMS.map((item) => {
            const active = pathname.startsWith(item.to)
            return (
              <Link
                key={item.to}
                to={item.to}
                className={`flex items-center gap-2.5 rounded-md px-3 py-2 text-sm font-medium transition-colors
                  ${active ? 'bg-moss-50 text-moss-700' : 'text-ink-soft hover:bg-moss-50 hover:text-ink'}`}
              >
                <item.icon className="h-4 w-4 shrink-0" />
                {item.label}
              </Link>
            )
          })}
          {isAdmin && (
            <Link
              to="/admin"
              className={`flex items-center gap-2.5 rounded-md px-3 py-2 text-sm font-medium transition-colors
                ${pathname.startsWith('/admin') ? 'bg-moss-50 text-moss-700' : 'text-ink-soft hover:bg-moss-50 hover:text-ink'}`}
            >
              <ShieldIcon className="h-4 w-4 shrink-0" />
              Admin Dashboard
            </Link>
          )}
        </nav>

        <div className="border-t border-hairline p-3">
          <div className="mb-2 truncate px-2 text-xs text-ink-muted">{name ?? 'Farmer'}</div>
          <ThemeToggle className="w-full justify-start" />
          <button
            onClick={() => {
              logout()
              navigate({ to: '/login' })
            }}
            className="w-full rounded-md px-3 py-2 text-left text-sm text-ink-soft hover:bg-terracotta-100 hover:text-terracotta-600"
          >
            Sign out
          </button>
        </div>
      </aside>

      <main className="flex-1 overflow-y-auto">{children}</main>
    </div>
  )
}

function LeafIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className}>
      <path
        d="M20 4c-8 0-14 5-14 13 0 1.5 1 3 3 3 8 0 13-6 13-14 0-.7-.05-1.4-.15-2H20Z"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      <path d="M9 20c2-5 5-8.5 10.5-14" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  )
}

function ChatIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className}>
      <path
        d="M4 5.5A2.5 2.5 0 0 1 6.5 3h11A2.5 2.5 0 0 1 20 5.5v8A2.5 2.5 0 0 1 17.5 16H10l-4.5 4v-4h-1A2.5 2.5 0 0 1 2 13.5v-8Z"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function ShieldIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className}>
      <path
        d="M12 3.5 5 6v5.5c0 4.4 3 8.2 7 9.5 4-1.3 7-5.1 7-9.5V6l-7-2.5Z"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      <path d="m9 12 2 2 4-4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}
