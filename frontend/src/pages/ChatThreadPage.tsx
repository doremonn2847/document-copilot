import { useEffect, useState } from 'react'
import type { ChatMessage } from '@/lib/chat-parts'
import { useLocation } from 'react-router-dom'
import ChatConversation from '@/components/chat/ChatConversation'
import { Button } from '@/components/ui/button'
import { chatError, firstMessage, messageHistory } from '@/lib/chats'
import { useAuth } from '@/lib/auth'
import { chatDocumentId, clearPending, readPending, savedQuestionId } from '@/lib/pending-chat'

export default function ChatThreadPage({ threadId, active, onSaved, onPendingChange }: {
  threadId: string; active: boolean; onSaved: () => void; onPendingChange: (threadId: string, pending: boolean) => void
}) {
  const location = useLocation()
  const { session } = useAuth()
  const userId = session!.user.id
  const [initial] = useState(() => {
    const state: unknown = location.state
    return typeof state === 'object' && state !== null && 'documentId' in state && state.documentId === chatDocumentId
      ? firstMessage(state) : null
  })
  const [recovered, setRecovered] = useState(() => readPending(userId, threadId))
  const [history, setHistory] = useState<ChatMessage[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [revision, setRevision] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    void messageHistory(threadId, controller.signal).then(async (data) => {
      const question = readPending(userId, threadId)
      const savedId = question ? await savedQuestionId(threadId, question.id) : null
      if (controller.signal.aborted) return
      if (savedId && data.some((message) => message.id === savedId)) {
        clearPending(userId, threadId); setRecovered(null)
      }
      if (!controller.signal.aborted) { setHistory(data); setError(null) }
    }).catch((cause: unknown) => { if (!controller.signal.aborted) setError(chatError(cause)) })
    return () => controller.abort()
  }, [threadId, userId, revision])
  if (error) return <div className="space-y-4 p-6"><p role="alert">{error}</p><Button onClick={() => setRevision((value) => value + 1)}>Retry history</Button></div>
  if (!history) return <p role="status" className="p-6">Loading conversation…</p>
  return <ChatConversation threadId={threadId} active={active} onSaved={onSaved} onPendingChange={onPendingChange} history={history} initial={recovered ? initial : null} recovered={initial ? null : recovered} />
}
