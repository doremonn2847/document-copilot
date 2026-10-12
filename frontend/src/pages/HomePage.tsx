import { useAuth } from '@/lib/auth'
import LogoutButton from '@/components/LogoutButton'

export default function HomePage() {
  const { session } = useAuth()
  return (
    <main className="min-h-screen bg-background px-6 py-20 text-foreground">
      <div className="mx-auto max-w-2xl space-y-6">
        <p className="text-sm font-medium tracking-widest text-muted-foreground uppercase">Document Copilot</p>
        <h1 className="text-4xl font-semibold tracking-tight sm:text-5xl">Answers grounded in your documents.</h1>
        <p className="text-lg text-muted-foreground">Your account is approved. The document and chat workspace is coming next.</p>
        <p className="text-sm text-muted-foreground">Signed in as {session?.user.email}</p>
        <LogoutButton />
      </div>
    </main>
  )
}
