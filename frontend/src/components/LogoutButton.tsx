import { useState } from 'react'
import { supabase } from '@/lib/supabase'
import { Button } from '@/components/ui/button'

export default function LogoutButton() {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function logout() {
    setBusy(true)
    setError(null)
    try {
      const { error: signOutError } = await supabase.auth.signOut({ scope: 'local' })
      if (signOutError) setError('Could not sign out. Try again.')
    } catch {
      setError('Could not sign out. Try again.')
    } finally { setBusy(false) }
  }

  return (
    <div className="space-y-2">
      <Button variant="outline" disabled={busy} onClick={() => void logout()}>{busy ? 'Signing out…' : 'Sign out'}</Button>
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
    </div>
  )
}
