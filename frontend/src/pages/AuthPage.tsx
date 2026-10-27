import { useState, type SubmitEvent } from 'react'
import { Link } from 'react-router-dom'
import { supabase } from '@/lib/supabase'
import AuthLayout from '@/components/AuthLayout'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useAuth } from '@/lib/auth'

export default function AuthPage({ mode }: { mode: 'login' | 'signup' }) {
  const signup = mode === 'signup'
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [submitted, setSubmitted] = useState(false)
  const { checkApproval } = useAuth()

  async function tryDemo() {
    setBusy(true); setError(null)
    try {
      const { data, error: sessionError } = await supabase.auth.getSession()
      if (sessionError) throw sessionError
      // Never replace a registered session with a guest identity.
      if (data.session) { checkApproval(); return }
      const { error: signInError } = await supabase.auth.signInAnonymously()
      if (signInError) throw signInError
    } catch {
      setError('The demo is currently unavailable. Try again later or use an approved account.')
    } finally { setBusy(false) }
  }

  async function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = event.currentTarget
    const fields = new FormData(form)
    const email = String(fields.get('email')).trim()
    const password = String(fields.get('password'))
    if (signup && password !== fields.get('confirmPassword')) {
      setError('The passwords do not match.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      const result = signup
        ? await supabase.auth.signUp({ email, password, options: { emailRedirectTo: `${window.location.origin}/auth/callback` } })
        : await supabase.auth.signInWithPassword({ email, password })
      if (result.error) {
        const code = result.error.code
        setError(code === 'email_not_confirmed'
          ? 'Confirm your email before signing in. Check your inbox for the confirmation link.'
          : code === 'over_email_send_rate_limit' || code === 'over_request_rate_limit'
            ? 'Too many requests. Wait a few minutes and try again.'
            : signup
              ? 'Could not create the account. Check your email and password, or sign in if you already registered.'
              : 'Could not sign in. Check your email and password and try again.')
        return
      }
      form.reset()
      if (signup) setSubmitted(true)
    } catch {
      setError('Cannot reach the sign-in service. Check your connection and try again.')
    } finally { setBusy(false) }
  }

  if (submitted) return (
    <AuthLayout title="Check your email">
      <p className="text-muted-foreground">If registration is available for this email, you will receive a confirmation link. Open it to confirm your email, then sign in.</p>
      <p className="text-sm text-muted-foreground">An administrator must approve your account before you can access documents or conversations.</p>
      <Link to="/login" className="inline-block font-medium underline underline-offset-4">Go to sign in</Link>
    </AuthLayout>
  )

  return (
    <AuthLayout title={signup ? 'Create your account' : 'Sign in'}>
      <p className="text-muted-foreground">{signup ? 'Confirm your email, then wait for an administrator to approve your access.' : 'Access your documents and private conversations.'}</p>
      {!signup && <div className="space-y-2 rounded-md border p-4">
        <Button type="button" variant="outline" className="w-full" disabled={busy} onClick={() => void tryDemo()}>Try demo</Button>
        <p className="text-sm text-muted-foreground">No account needed. Up to 3 generated attempts per browser identity, subject to shared daily availability. Stopped or failed generations can use an attempt.</p>
      </div>}
      <form onSubmit={(event) => void submit(event)} className="space-y-5" aria-busy={busy}>
        <div className="space-y-2">
          <Label htmlFor="email">Email</Label>
          <Input id="email" name="email" type="email" autoComplete="email" required disabled={busy} />
        </div>
        <div className="space-y-2">
          <Label htmlFor="password">Password</Label>
          <Input id="password" name="password" type="password" autoComplete={signup ? 'new-password' : 'current-password'} minLength={signup ? 8 : undefined} required disabled={busy} aria-describedby={signup ? 'password-hint' : undefined} />
          {signup && <p id="password-hint" className="text-sm text-muted-foreground">Use at least 8 characters.</p>}
        </div>
        {signup && <div className="space-y-2">
          <Label htmlFor="confirmPassword">Confirm password</Label>
          <Input id="confirmPassword" name="confirmPassword" type="password" autoComplete="new-password" minLength={8} required disabled={busy} />
        </div>}
        {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
        <Button type="submit" disabled={busy} className="w-full" size="lg">{busy ? 'Please wait…' : signup ? 'Create account' : 'Sign in'}</Button>
      </form>
      <p className="text-sm text-muted-foreground">
        {signup ? 'Already registered? ' : 'Need an account? '}
        <Link to={signup ? '/login' : '/signup'} className="font-medium text-foreground underline underline-offset-4">{signup ? 'Sign in' : 'Create an account'}</Link>
      </p>
    </AuthLayout>
  )
}
