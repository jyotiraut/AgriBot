import { createFileRoute, Outlet, redirect } from '@tanstack/react-router'
import { useAuth } from '@/lib/auth'
import { AppShell } from '@/components/AppShell'

export const Route = createFileRoute('/_app')({
  beforeLoad: () => {
    if (!useAuth.getState().token) {
      throw redirect({ to: '/login' })
    }
  },
  component: () => (
    <AppShell>
      <Outlet />
    </AppShell>
  ),
})
