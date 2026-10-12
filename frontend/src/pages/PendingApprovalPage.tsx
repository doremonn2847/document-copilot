import { useAuth } from '@/lib/auth'
import AuthLayout from '@/components/AuthLayout'
import LogoutButton from '@/components/LogoutButton'
import { Button } from '@/components/ui/button'

export default function PendingApprovalPage() {
  const { session, checkApproval } = useAuth()
  return (
    <AuthLayout title="Your account is awaiting approval">
      <p className="text-muted-foreground">You are signed in as <span className="font-medium text-foreground">{session?.user.email}</span>. An administrator must approve your access before you can use Document Copilot.</p>
      <p className="text-sm text-muted-foreground">Contact your administrator to request access. If they have already approved your account, check again below.</p>
      <Button onClick={checkApproval}>Check again</Button>
      <LogoutButton />
    </AuthLayout>
  )
}
