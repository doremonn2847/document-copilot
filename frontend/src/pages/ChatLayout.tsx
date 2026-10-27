import { useCallback, useState } from 'react'
import { Outlet, useMatch } from 'react-router-dom'
import ThreadSidebar from '@/components/chat/ThreadSidebar'
import ChatThreadPage from '@/pages/ChatThreadPage'
import { useAuth } from '@/lib/auth'
import DemoBanner from '@/components/chat/DemoBanner'

export default function ChatLayout() {
  const { session } = useAuth()
  return <Workspace key={session!.user.id} />
}

function Workspace() {
  const { isDemo } = useAuth()
  const threadId = useMatch('/chats/:threadId')?.params.threadId
  const [revision, setRevision] = useState(0)
  const [previousThreadId, setPreviousThreadId] = useState(threadId)
  const [sessions, setSessions] = useState(() => threadId ? [{ id: threadId, pending: false }] : [])
  const onSaved = useCallback(() => setRevision((value) => value + 1), [])
  if (previousThreadId !== threadId) {
    setPreviousThreadId(threadId)
    setSessions((current) => {
      const retained = current.filter((item) => item.id === threadId || item.pending)
      if (threadId && !retained.some((item) => item.id === threadId)) retained.push({ id: threadId, pending: false })
      return retained
    })
  }
  const onPendingChange = useCallback((id: string, pending: boolean) => {
    setSessions((current) => {
      if (!current.some((item) => item.id === id && item.pending !== pending)) return current
      return current.map((item) => item.id === id ? { ...item, pending } : item)
        .filter((item) => item.id === threadId || item.pending)
    })
  }, [threadId])
  return (
    <div className="flex h-dvh flex-col bg-background text-foreground md:flex-row">
      <ThreadSidebar revision={revision} />
      <main className="flex min-h-0 min-w-0 flex-1 flex-col">
        {isDemo && <DemoBanner revision={revision} />}
        <div className="min-h-0 flex-1">
        {sessions.map((item) => <div key={item.id} hidden={item.id !== threadId} className="h-full">
          <ChatThreadPage threadId={item.id} active={item.id === threadId} onSaved={onSaved} onPendingChange={onPendingChange} />
        </div>)}
        {!threadId && <Outlet />}
        </div>
      </main>
    </div>
  )
}
