import { createFileRoute, redirect } from '@tanstack/react-router'
import { useAuth } from '@/lib/auth'

export const Route = createFileRoute('/')({
  beforeLoad: () => {
    throw redirect({ to: useAuth.getState().token ? '/market' : '/login' })
  },
})
