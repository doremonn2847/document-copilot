import { useEffect, useState } from 'react'
import type { UIMessage } from 'ai'
import { useLocation, useParams } from 'react-router-dom'
import ChatConversation from '@/components/chat/ChatConversation'
import { Button } from '@/components/ui/button'
import { chatError, firstMessage, messageHistory } from '@/lib/chats'
import { useAuth } from '@/lib/auth'
import { chatDocumentId, clearPending, readPending, savedQuestionId } from '@/lib/pending-chat'

export default function ChatThreadPage() {
  const { threadId = '' } = useParams()
  return <ThreadHistory key={threadId} threadId={threadId} />
}

function ThreadHistory({ threadId }: { threadId: string }) {
  const location = useLocation()
  const { session } = useAuth()
  const userId = session!.user.id
  const [initial] = useState(() => {
    const state: unknown = location.state
    return typeof state === 'object' && state !== null && 'documentId' in state && state.documentId === chatDocumentId
      ? firstMessage(state) : null
  })
  const [recovered, setRecovered] = useState(() => readPending(userId, threadId))
  const [history, setHistory] = useState<UIMessage[] | null>(null)
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
  return <ChatConversation threadId={threadId} history={history} initial={recovered ? initial : null} recovered={initial ? null : recovered} />
}
