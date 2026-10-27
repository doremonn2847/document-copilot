import { useEffect, useRef, useState, type ReactNode } from 'react'
import type { Session } from '@supabase/supabase-js'
import { AuthContext, type AccessStatus } from '@/lib/auth'
import { api } from '@/lib/api'
import { ApiError } from '@/lib/http'
import { supabase } from '@/lib/supabase'

export default function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null)
  const [restored, setRestored] = useState(false)
  const [status, setStatus] = useState<AccessStatus>('loading')
  const [error, setError] = useState<string | null>(null)
  const [isDemo, setIsDemo] = useState(false)
  const [revision, setRevision] = useState(0)
  const identity = useRef<string | null>(null)
  const approvedUser = useRef<string | null>(null)

  useEffect(() => {
    let active = true
    let receivedEvent = false
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, next) => {
      receivedEvent = true
      // Keep callbacks synchronous: Supabase holds its auth lock here.
      setSession(next)
      setRestored(true)
      if (!next || next.user.id !== identity.current) {
        setStatus(next ? 'loading' : 'signed-out')
        setIsDemo(false)
      }
      identity.current = next?.user.id ?? null
      setError(null)
      if (next) setRevision((value) => value + 1)
    })
    void supabase.auth.getSession().then(({ data, error: restoreError }) => {
      if (!active || receivedEvent) return
      setSession(data.session)
      identity.current = data.session?.user.id ?? null
      setRestored(true)
      setStatus(data.session ? 'loading' : 'signed-out')
      if (restoreError) {
        setStatus('error')
        setError('Your session could not be restored. Reload the page or sign in again.')
      }
    })
    return () => { active = false; subscription.unsubscribe() }
  }, [])

  useEffect(() => {
    if (!restored || !session) return
    const controller = new AbortController()
    async function approvedProfile() {
      try { return await api.get<unknown>('/auth/me', controller.signal) }
      catch (cause) {
        if (!(cause instanceof ApiError) || cause.status !== 403 || !session!.user.is_anonymous) throw cause
        await api.post('/auth/demo', undefined, controller.signal)
        return api.get<unknown>('/auth/me', controller.signal)
      }
    }
    void approvedProfile().then((user) => {
      if (controller.signal.aborted) return
      if (typeof user !== 'object' || user === null || !('id' in user) || !('email' in user)
        || !('is_demo' in user) || typeof user.is_demo !== 'boolean'
        || user.id !== session.user.id || user.is_demo !== Boolean(session.user.is_anonymous)
        || (user.is_demo ? user.email !== null : typeof user.email !== 'string')) {
        throw new Error('Invalid authentication response')
      }
      approvedUser.current = session.user.id
      setIsDemo(user.is_demo)
      setStatus('approved')
    }).catch((cause: unknown) => {
      if (controller.signal.aborted) return
      if (cause instanceof ApiError && cause.status === 403) {
        approvedUser.current = null
        setStatus(session.user.is_anonymous ? 'error' : 'pending')
        if (session.user.is_anonymous) setError('The demo is unavailable. Try again later or sign in with an approved account.')
      } else if (cause instanceof ApiError && cause.status === 401) {
        approvedUser.current = null
        setSession(null)
        setStatus('signed-out')
        void supabase.auth.signOut({ scope: 'local' })
      } else if (approvedUser.current === session.user.id) {
        // Token refreshes (e.g. on tab refocus) re-check access. A transient
        // failure must not unmount the workspace and abort running answers.
        return
      } else {
        setStatus('error')
        setError(cause instanceof ApiError && cause.isNetworkError
          ? cause.message : 'We could not check your access. Try again in a moment.')
      }
    })
    return () => controller.abort()
  }, [session, restored, revision])

  return (
    <AuthContext.Provider value={{ session, status, error, isDemo, checkApproval: () => {
      setStatus('loading')
      setError(null)
      setRevision((value) => value + 1)
    } }}>
      {children}
    </AuthContext.Provider>
  )
}
