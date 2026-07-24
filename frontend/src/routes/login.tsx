import { useState, type FormEvent } from 'react'
import { createFileRoute, Link, useNavigate } from '@tanstack/react-router'
import { login } from '@/lib/api'
import { useAuth } from '@/lib/auth'
import { Button } from '@/components/ui/Button'
import { Field, Input } from '@/components/ui/Input'
import { Card } from '@/components/ui/Card'
import { AuthPageFrame } from '@/components/AuthPageFrame'

export const Route = createFileRoute('/login')({
  component: LoginPage,
})

function LoginPage() {
  const navigate = useNavigate()
  const setAuth = useAuth((s) => s.setAuth)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const res = await login(email, password)
      setAuth(res.access_token, res.user_id, email.split('@')[0], email)
      navigate({ to: '/market' })
    } catch {
      setError('Could not sign in — check your email and password.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthPageFrame>
      <Card className="w-full max-w-sm p-7">
        <h1 className="font-display text-2xl font-semibold text-ink">Welcome back</h1>
        <p className="mt-1 text-sm text-ink-soft">Sign in to your KrishiMitra account.</p>

        <form onSubmit={onSubmit} className="mt-6 space-y-4">
          <div>
            <Field htmlFor="email">Email</Field>
            <Input
              id="email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
            />
          </div>
          <div>
            <Field htmlFor="password">Password</Field>
            <Input
              id="password"
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
            />
          </div>
          {error && <p className="text-sm text-critical">{error}</p>}
          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? 'Signing in…' : 'Sign in'}
          </Button>
        </form>

        <p className="mt-5 text-center text-sm text-ink-soft">
          New here?{' '}
          <Link to="/register" className="font-medium text-moss-600 hover:underline">
            Create an account
          </Link>
        </p>
      </Card>
    </AuthPageFrame>
  )
}
