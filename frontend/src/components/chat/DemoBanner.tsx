import { useEffect, useState } from 'react'
import { api } from '@/lib/api'

type DemoStatus = {
  remaining_attempts: number
  can_generate: boolean
  reset_at: string
  reason: 'visitor_limit' | 'daily_budget' | 'busy' | 'unavailable' | null
}

function parseStatus(value: unknown): DemoStatus {
  if (typeof value !== 'object' || !value || !('remaining_attempts' in value)
    || typeof value.remaining_attempts !== 'number' || !Number.isInteger(value.remaining_attempts)
    || value.remaining_attempts < 0 || value.remaining_attempts > 3
    || !('can_generate' in value) || typeof value.can_generate !== 'boolean'
    || !('reset_at' in value) || typeof value.reset_at !== 'string' || !Number.isFinite(Date.parse(value.reset_at))
    || !('reason' in value) || (value.reason !== null && value.reason !== 'visitor_limit'
      && value.reason !== 'daily_budget' && value.reason !== 'busy' && value.reason !== 'unavailable')) {
    throw new Error('Invalid demo status')
  }
  return value as DemoStatus
}

export default function DemoBanner({ revision }: { revision: number }) {
  const [status, setStatus] = useState<DemoStatus | null>(null)
  const [unavailable, setUnavailable] = useState(false)
  useEffect(() => {
    const controller = new AbortController()
    let pending = false
    async function refresh() {
      if (pending) return
      pending = true
      try {
        const next = parseStatus(await api.get<unknown>('/auth/demo', controller.signal))
        if (!controller.signal.aborted) { setStatus(next); setUnavailable(false) }
      } catch {
        if (!controller.signal.aborted) setUnavailable(true)
      } finally { pending = false }
    }
    void refresh()
    const timer = setInterval(() => void refresh(), 15_000)
    const focus = () => void refresh()
    window.addEventListener('focus', focus)
    return () => { controller.abort(); clearInterval(timer); window.removeEventListener('focus', focus) }
  }, [revision])
  const reasons = {
    visitor_limit: 'This identity has used its generation allowance. Saved chats and feedback remain available.',
    daily_budget: `The shared daily pool is unavailable. Next reset: ${status ? new Date(status.reset_at).toLocaleString() : ''}.`,
    busy: 'One reply is already running for this identity.',
    unavailable: 'New demo replies are temporarily unavailable. Saved chats remain accessible.',
  }
  return <aside aria-label="Demo allowance" className="border-b bg-muted px-4 py-2 text-sm">
    <p role="status">Demo · {unavailable ? 'Allowance could not be checked.' : status ? `${status.remaining_attempts} generated attempts remaining. ${status.reason ? reasons[status.reason] : 'Shared daily availability applies.'}` : 'Checking allowance…'}</p>
    <p className="text-xs text-muted-foreground">History belongs to this browser identity. Signing out or clearing browser data may lose access. Attempts do not reset daily; stopped or failed generations can consume one.</p>
  </aside>
}
