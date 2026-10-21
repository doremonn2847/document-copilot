import { useNavigate } from 'react-router-dom'
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import MessageComposer from '@/components/chat/MessageComposer'
import { api } from '@/lib/api'
import { chatError, parseThread } from '@/lib/chats'
import { useAuth } from '@/lib/auth'
import { chatDocumentId, clearCreation, readCreation, saveCreation, savePending, type PendingCreation } from '@/lib/pending-chat'

// Each example was answered and checked against its cited quotes on 2026-10-22.
const EXAMPLES = [
  'What does Microsoft say Azure provides in the 2025 corpus filing?',
  'How does Amazon describe AWS in its 2025 corpus filing?',
  'What risks does Alphabet describe about artificial intelligence in its 2025 corpus filing?',
  'How did NVIDIA describe demand for its Data Center products in its 2025 corpus filing?',
]

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
        <p className="max-w-lg text-sm text-muted-foreground">The corpus holds 10-K filings for Apple, Amazon, Alphabet, Microsoft and NVIDIA, corpus years 2021–2025. Answers cite the passages they rely on and say what the filings do not establish.</p>
        {!creation && <section aria-label="Example questions" className="space-y-2">
          <h2 className="text-sm font-semibold">Try an example</h2>
          <ul className="grid gap-2 sm:grid-cols-2">{EXAMPLES.map((example) => <li key={example}>
            <button type="button" disabled={busy} onClick={() => void firstSend(example)}
              className="h-full w-full rounded-md border p-3 text-left text-sm hover:bg-muted focus-visible:outline focus-visible:outline-2 disabled:opacity-50">{example}</button>
          </li>)}</ul>
        </section>}
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
