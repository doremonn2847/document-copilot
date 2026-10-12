import { useNavigate } from 'react-router-dom'
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import MessageComposer from '@/components/chat/MessageComposer'
import { api } from '@/lib/api'
import { chatError, parseThread } from '@/lib/chats'
import { useAuth } from '@/lib/auth'
import { chatDocumentId, clearCreation, readCreation, saveCreation, savePending, type PendingCreation } from '@/lib/pending-chat'

export default function NewChatPage() {
  const navigate = useNavigate()
  const { session } = useAuth()
  const userId = session!.user.id
  const [creation, setCreation] = useState(() => readCreation(userId))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function create(question: PendingCreation) {
    setBusy(true); setError(null)
    try {
      const thread = parseThread(await api.post<unknown>('/chat/threads', { id: question.threadId, title: question.text.slice(0, 255) }))
      if (thread.id !== question.threadId) throw new Error('Unexpected thread ID')
      clearCreation(userId)
      navigate(`/chats/${thread.id}`, { state: { firstMessage: question, documentId: chatDocumentId } })
    } catch (cause) { setError(chatError(cause)) }
    finally { setBusy(false) }
  }

  async function firstSend(text: string) {
    const question = { id: crypto.randomUUID(), threadId: crypto.randomUUID(), text }
    saveCreation(userId, question)
    savePending(userId, question.threadId, question)
    setCreation(question)
    await create(question)
  }

  return (
    <div className="mx-auto flex h-full max-w-3xl flex-col px-6 py-6">
      <div className="flex flex-1 flex-col justify-center gap-4 pb-8">
        <h1 className="text-3xl font-semibold tracking-tight">Start a conversation</h1>
        <p className="max-w-lg text-muted-foreground">Ask about SEC filings, or reopen a conversation from the sidebar. Your new chat is saved when you send the first question.</p>
      </div>
      {creation && <div className="mb-4 space-y-3"><p className="whitespace-pre-wrap">{creation.text}</p>
        <p className="text-sm text-muted-foreground">Your submitted question is retained until the conversation is ready.</p>
        <Button disabled={busy} onClick={() => void create(creation)}>{busy ? 'Creating conversation…' : 'Retry question'}</Button>
      </div>}
      {error && <p role="alert" className="mb-3 text-destructive">{error}</p>}
      <MessageComposer onSend={firstSend} blocked={creation !== null} />
    </div>
  )
}
