import { useEffect, useRef, useState } from 'react'
import { useChat } from '@ai-sdk/react'
import { DefaultChatTransport, type UIMessage } from 'ai'
import { useLocation, useNavigate, useOutletContext } from 'react-router-dom'
import MessageComposer from '@/components/chat/MessageComposer'
import MessageList from '@/components/chat/MessageList'
import { Button } from '@/components/ui/button'
import { chatError, type FirstMessage } from '@/lib/chats'
import { env } from '@/lib/env'
import { streamFetch } from '@/lib/http'
import type { ChatLayoutContext } from '@/pages/ChatLayout'
import { useAuth } from '@/lib/auth'
import { clearPending, savePending } from '@/lib/pending-chat'

export default function ChatConversation({ threadId, history, initial, recovered }: {
  threadId: string; history: UIMessage[]; initial: FirstMessage | null; recovered: FirstMessage | null
}) {
  const { session } = useAuth()
  const userId = session!.user.id
  const { onSaved } = useOutletContext<ChatLayoutContext>()
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const completed = useRef(history)
  const [recoveredQuestion] = useState<UIMessage | null>(() => recovered ? { id: recovered.id, role: 'user', parts: [{ type: 'text', text: recovered.text }] } : null)
  const pending = useRef<UIMessage | null>(recoveredQuestion)
  const started = useRef(false)
  const bottom = useRef<HTMLDivElement>(null)
  const [failure, setFailure] = useState<string | null>(recovered ? 'The page was reloaded before this reply was confirmed. Retry your question.' : null)
  const [transport] = useState(() => new DefaultChatTransport({
    api: `${env.apiBaseUrl}/chat/stream`, fetch: streamFetch,
    prepareSendMessagesRequest: ({ messages }) => ({ body: { threadId, messages: [messages.findLast((message) => message.role === 'user')] } }),
  }))
  const { messages, setMessages, sendMessage, clearError, stop, status } = useChat({
    id: threadId, messages: recoveredQuestion ? [...history, recoveredQuestion] : history, transport,
    onError: (error) => setFailure(chatError(error)),
    onFinish: ({ messages: finished, isAbort, isDisconnect, isError, finishReason }) => {
      if (!isAbort && !isDisconnect && !isError && finishReason === 'stop') {
        clearPending(userId, threadId)
        completed.current = finished; pending.current = null; setFailure(null); onSaved()
      } else setFailure('Reply interrupted. Retry the same question to recover or finish the turn.')
    },
  })
  const busy = status === 'submitted' || status === 'streaming'

  async function send(text: string, id = crypto.randomUUID()) {
    savePending(userId, threadId, { id, text })
    const question: UIMessage = { id, role: 'user', parts: [{ type: 'text', text }] }
    pending.current = question
    setFailure(null)
    await sendMessage(question)
  }

  useEffect(() => {
    let active = true
    // Defer past StrictMode's rehearsal so it cannot cancel the initial send.
    queueMicrotask(() => {
      if (!active || started.current || !initial) return
      started.current = true
      navigate(pathname, { replace: true, state: null })
      const question: UIMessage = { id: initial.id, role: 'user', parts: [{ type: 'text', text: initial.text }] }
      pending.current = question
      void sendMessage(question)
    })
    return () => { active = false; void stop() }
  }, [initial, navigate, pathname, sendMessage, stop])

  useEffect(() => { bottom.current?.scrollIntoView({ block: 'end' }) }, [messages, status])

  async function retry() {
    if (!pending.current || busy) return
    setMessages(completed.current); clearError(); setFailure(null)
    await sendMessage(pending.current)
  }

  return <div className="mx-auto flex h-full max-w-3xl flex-col px-6 py-6">
    <header className="mb-4 border-b pb-4"><h1 className="font-semibold">Conversation</h1><p className="text-xs text-muted-foreground">Private to your account</p></header>
    <div className="min-h-0 flex-1 overflow-y-auto pb-6">
      {!messages.length && <p className="py-8 text-muted-foreground">Send a question to start this conversation.</p>}
      <MessageList messages={messages} provisional={busy || failure !== null} />
      <div ref={bottom} />
    </div>
    <div aria-live="polite" className="mb-3 text-sm">
      {busy && <p className="text-muted-foreground">{status === 'submitted' ? 'Waiting for reply…' : 'Receiving reply…'}</p>}
      {failure && <div className="space-y-2"><p role="alert" className="text-destructive">{failure}</p><Button variant="outline" disabled={busy} onClick={() => void retry()}>Retry question</Button></div>}
    </div>
    <MessageComposer onSend={send} busy={busy} blocked={failure !== null} onStop={() => {
      setFailure('Reply stopped. Retry the same question to recover or finish the turn.')
      void stop()
    }} />
  </div>
}
