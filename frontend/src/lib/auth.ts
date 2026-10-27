import { createContext, useContext } from 'react'
import type { Session } from '@supabase/supabase-js'

export type AccessStatus = 'loading' | 'signed-out' | 'pending' | 'approved' | 'error'

export type AuthContextValue = {
  session: Session | null
  status: AccessStatus
  error: string | null
  isDemo: boolean
  checkApproval: () => void
}

export const AuthContext = createContext<AuthContextValue | null>(null)

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside AuthProvider')
  return context
}
