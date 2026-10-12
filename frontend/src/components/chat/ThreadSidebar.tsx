import { useEffect, useRef, useState } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import LogoutButton from '@/components/LogoutButton'
import { chatError, threadPage, type Thread } from '@/lib/chats'

export default function ThreadSidebar({ revision }: { revision: number }) {
  const { pathname } = useLocation()
  const [threads, setThreads] = useState<Thread[]>([])
  const [error, setError] = useState<string | null>(null)
  const [more, setMore] = useState(false)
  const [busy, setBusy] = useState(false)
  const [retry, setRetry] = useState(0)
  const generation = useRef(0)

  useEffect(() => {
    const controller = new AbortController()
    generation.current += 1
    void threadPage(0, controller.signal).then((page) => {
      if (controller.signal.aborted) return
      setThreads(page); setMore(page.length === 50); setError(null)
    }).catch((cause: unknown) => { if (!controller.signal.aborted) setError(chatError(cause)) })
    return () => { generation.current += 1; controller.abort() }
  }, [revision, pathname, retry])

  async function loadMore() {
    const currentGeneration = generation.current
    setBusy(true)
    try {
      const page = await threadPage(threads.length)
      if (currentGeneration !== generation.current) return
      setThreads((current) => [...current, ...page.filter((thread) => !current.some((item) => item.id === thread.id))])
      setMore(page.length === 50); setError(null)
    } catch (cause) { if (currentGeneration === generation.current) setError(chatError(cause)) }
    finally { setBusy(false) }
  }

  return (
    <aside className="flex max-h-64 flex-col border-b bg-muted/30 p-4 md:max-h-none md:w-64 md:shrink-0 md:border-r md:border-b-0">
      <p className="font-semibold">Document Copilot</p>
      <p className="mb-5 text-xs text-muted-foreground">SEC filing assistant</p>
      <NavLink to="/chats" end className="rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground">New chat</NavLink>
      <nav aria-label="Conversations" className="my-5 flex-1 space-y-1 overflow-y-auto">
        <p className="mb-3 px-2 text-xs text-muted-foreground">Conversations</p>
        {!threads.length && !error && <p className="px-2 text-sm text-muted-foreground">No conversations yet.</p>}
        {threads.map((thread) => <NavLink key={thread.id} to={`/chats/${thread.id}`} className={({ isActive }) =>
          `block truncate rounded-lg px-3 py-2 text-sm ${isActive ? 'bg-accent font-medium' : 'hover:bg-accent/60'}`} title={thread.title}>{thread.title}</NavLink>)}
        {more && <Button variant="ghost" disabled={busy} onClick={() => void loadMore()}>Load more</Button>}
        {error && <div className="space-y-2 px-2"><p role="alert" className="text-sm text-destructive">{error}</p><Button variant="outline" onClick={() => setRetry((value) => value + 1)}>Retry list</Button></div>}
      </nav>
      <LogoutButton />
    </aside>
  )
}
