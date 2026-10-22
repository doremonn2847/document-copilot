import { useEffect, useRef, useState } from 'react'
import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import { Pencil, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import LogoutButton from '@/components/LogoutButton'
import { useAuth } from '@/lib/auth'
import { chatError, deleteThread, renameThread, threadPage, type Thread } from '@/lib/chats'
import { ApiError } from '@/lib/http'
import { clearPending } from '@/lib/pending-chat'

export default function ThreadSidebar({ revision }: { revision: number }) {
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const { session } = useAuth()
  const [threads, setThreads] = useState<Thread[]>([])
  const [error, setError] = useState<string | null>(null)
  const [more, setMore] = useState(false)
  const [busy, setBusy] = useState(false)
  const [deleting, setDeleting] = useState<string | null>(null)
  // Shown under the row the analyst acted on, not at the end of a long list.
  const [rowError, setRowError] = useState<{ id: string; text: string } | null>(null)
  const [retry, setRetry] = useState(0)
  const [query, setQuery] = useState('')
  const [search, setSearch] = useState('')
  const [editing, setEditing] = useState<string | null>(null)
  // Enter and the blur that follows must save once.
  const renaming = useRef<string | null>(null)
  const generation = useRef(0)

  useEffect(() => {
    const timer = setTimeout(() => setSearch(query.trim()), 250)
    return () => clearTimeout(timer)
  }, [query])

  useEffect(() => {
    const controller = new AbortController()
    generation.current += 1
    void threadPage(0, controller.signal, search).then((page) => {
      if (controller.signal.aborted) return
      setThreads(page); setMore(page.length === 50); setError(null)
    }).catch((cause: unknown) => { if (!controller.signal.aborted) setError(chatError(cause)) })
    return () => { generation.current += 1; controller.abort() }
  }, [revision, pathname, retry, search])

  async function loadMore() {
    const currentGeneration = generation.current
    setBusy(true)
    try {
      const page = await threadPage(threads.length, undefined, search)
      if (currentGeneration !== generation.current) return
      setThreads((current) => [...current, ...page.filter((thread) => !current.some((item) => item.id === thread.id))])
      setMore(page.length === 50); setError(null)
    } catch (cause) { if (currentGeneration === generation.current) setError(chatError(cause)) }
    finally { setBusy(false) }
  }

  async function remove(thread: Thread) {
    if (!window.confirm(`Delete "${thread.title}"? This permanently removes the conversation and cannot be undone.`)) return
    setDeleting(thread.id)
    setRowError(null)
    try {
      await deleteThread(thread.id)
      setThreads((current) => current.filter((item) => item.id !== thread.id))
      clearPending(session!.user.id, thread.id)
      if (pathname === `/chats/${thread.id}`) navigate('/chats', { replace: true })
    } catch (cause) {
      setRowError({
        id: thread.id,
        text: cause instanceof ApiError && cause.status === 409
          ? 'This conversation is still answering. Delete it after the reply finishes.'
          : chatError(cause),
      })
    }
    finally { setDeleting(null) }
  }

  function startRename(thread: Thread) {
    renaming.current = thread.id
    setEditing(thread.id)
    setRowError(null)
  }

  async function rename(thread: Thread, title: string) {
    if (renaming.current !== thread.id) return
    renaming.current = null
    setEditing(null)
    const next = title.trim()
    if (!next || next === thread.title) return
    try {
      const saved = await renameThread(thread.id, next)
      setThreads((current) => current.map((item) => (item.id === saved.id ? { ...item, title: saved.title } : item)))
    } catch (cause) {
      setRowError({ id: thread.id, text: chatError(cause) })
    }
  }

  return (
    <aside className="flex max-h-64 flex-col border-b bg-muted/30 p-4 md:max-h-none md:w-64 md:shrink-0 md:border-r md:border-b-0">
      <p className="font-semibold">Document Copilot</p>
      <p className="mb-5 text-xs text-muted-foreground">SEC filing assistant</p>
      <NavLink to="/chats" end className="rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground">New chat</NavLink>
      <nav aria-label="Conversations" className="my-5 flex-1 space-y-1 overflow-y-auto">
        <p className="mb-3 px-2 text-xs text-muted-foreground">Conversations</p>
        <Input type="search" value={query} maxLength={100} onChange={(event) => setQuery(event.target.value)}
          placeholder="Search titles" aria-label="Search conversation titles" className="mb-2" />
        {!threads.length && !error && <p className="px-2 text-sm text-muted-foreground">{search ? 'No conversation titles match.' : 'No conversations yet.'}</p>}
        {threads.map((thread) => <div key={thread.id}>
          <div className="group flex items-center gap-1">
          {editing === thread.id
            ? <form className="min-w-0 flex-1" onSubmit={(event) => { event.preventDefault(); void rename(thread, new FormData(event.currentTarget).get('title') as string) }}>
              <Input name="title" defaultValue={thread.title} maxLength={255} autoFocus aria-label="Conversation title"
                onFocus={(event) => event.currentTarget.select()}
                onBlur={(event) => void rename(thread, event.currentTarget.value)}
                onKeyDown={(event) => { if (event.key === 'Escape') { renaming.current = null; setEditing(null) } }} />
            </form>
            : <NavLink to={`/chats/${thread.id}`} className={({ isActive }) =>
              `block min-w-0 flex-1 truncate rounded-lg px-3 py-2 text-sm ${isActive ? 'bg-accent font-medium' : 'hover:bg-accent/60'}`} title={thread.title}>{thread.title}</NavLink>}
          <button type="button" onClick={() => startRename(thread)} hidden={editing === thread.id}
            aria-label={`Rename conversation ${thread.title}`} title="Rename conversation"
            className="shrink-0 rounded p-1.5 text-muted-foreground opacity-60 hover:bg-accent hover:text-foreground hover:opacity-100 focus-visible:opacity-100 focus-visible:outline focus-visible:outline-2 md:opacity-0 md:group-hover:opacity-60">
            <Pencil className="size-4" aria-hidden="true" />
          </button>
          <button type="button" disabled={deleting === thread.id} onClick={() => void remove(thread)}
            aria-label={`Delete conversation ${thread.title}`} title="Delete conversation"
            className="shrink-0 rounded p-1.5 text-muted-foreground opacity-60 hover:bg-accent hover:text-destructive hover:opacity-100 focus-visible:opacity-100 focus-visible:outline focus-visible:outline-2 disabled:opacity-30 md:opacity-0 md:group-hover:opacity-60">
            <Trash2 className="size-4" aria-hidden="true" />
          </button>
          </div>
          {rowError?.id === thread.id && <p role="alert" className="px-3 pb-1 text-xs text-destructive">{rowError.text}</p>}
        </div>)}
        {more && <Button variant="ghost" disabled={busy} onClick={() => void loadMore()}>Load more</Button>}
        {error && <div className="space-y-2 px-2"><p role="alert" className="text-sm text-destructive">{error}</p><Button variant="outline" onClick={() => setRetry((value) => value + 1)}>Retry list</Button></div>}
      </nav>
      <LogoutButton />
    </aside>
  )
}
