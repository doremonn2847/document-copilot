import { Link, Navigate } from 'react-router-dom'
import { useAuth } from '@/lib/auth'
import AuthLayout from '@/components/AuthLayout'

export default function AuthCallbackPage() {
  const { status } = useAuth()
  const params = new URLSearchParams(window.location.hash.slice(1))
  const query = new URLSearchParams(window.location.search)
  const failed = params.has('error') || query.has('error')
  if (failed) return (
    <AuthLayout title="The confirmation link could not be used">
      <p className="text-muted-foreground">The link may have expired or already been used. Try signing in if you previously confirmed your email.</p>
      <Link to="/login" className="underline underline-offset-4">Go to sign in</Link>
    </AuthLayout>
  )
  if (status === 'loading') return <AuthLayout title="Confirming your account"><p role="status">Please wait…</p></AuthLayout>
  return <Navigate to={status === 'signed-out' ? '/login' : '/'} replace />
}
