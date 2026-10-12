import type { ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '@/lib/auth'
import AuthLayout from '@/components/AuthLayout'
import LogoutButton from '@/components/LogoutButton'
import { Button } from '@/components/ui/button'

export default function AccessGate({ access, children }: { access: 'public' | 'approved' | 'pending'; children: ReactNode }) {
  const { status, error, session, checkApproval } = useAuth()
  if (status === 'loading') return <AuthLayout title="Checking your access"><p role="status">Please wait…</p></AuthLayout>
  if (status === 'error') return (
    <AuthLayout title="We could not check your access">
      <p role="alert" className="text-muted-foreground">{error}</p>
      <Button onClick={() => session ? checkApproval() : window.location.reload()}>Try again</Button>
      <LogoutButton />
    </AuthLayout>
  )
  if (status === 'signed-out') return access === 'public' ? children : <Navigate to="/login" replace />
  if (status === 'pending') return access === 'pending' ? children : <Navigate to="/pending-approval" replace />
  return access === 'approved' ? children : <Navigate to="/" replace />
}
