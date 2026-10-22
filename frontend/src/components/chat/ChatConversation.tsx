import { useEffect, useRef, useState } from 'react'
import { useChat } from '@ai-sdk/react'
import { DefaultChatTransport } from 'ai'
import type { ChatMessage } from '@/lib/chat-parts'
import { useNavigate } from 'react-router-dom'
import MessageComposer from '@/components/chat/MessageComposer'
import MessageList from '@/components/chat/MessageList'
import { Button } from '@/components/ui/button'
import { chatError, type FirstMessage } from '@/lib/chats'
import { env } from '@/lib/env'
import { streamFetch } from '@/lib/http'
import { useAuth } from '@/lib/auth'
import { clearPending, savePending } from '@/lib/pending-chat'

// Answers usually take 15–40 s; a static line can look stuck. Mounted per
// answer, so the count restarts with each question.
function BusyStatus({ progress }: { progress: string }) {
  const [seconds, setSeconds] = useState(0)
  useEffect(() => {
    const start = Date.now()
    const timer = setInterval(() => setSeconds(Math.floor((Date.now() - start) / 1000)), 1000)
    return () => clearInterval(timer)
  }, [])
  return <>
    {/* The ticking count is hidden from screen readers; the stage and the slow note are announced. */}
    <p className="text-muted-foreground">{progress} <span aria-hidden="true" className="tabular-nums">· {seconds} s</span></p>
    {seconds >= 45 && <p className="text-muted-foreground">This question is taking longer than usual. Answers can take up to two minutes; keep waiting or stop the reply.</p>}
  </>
}

export default function ChatConversation({ threadId, history, initial, recovered, active, onSaved, onPendingChange }: {
  threadId: string; history: ChatMessage[]; initial: FirstMessage | null; recovered: FirstMessage | null
  active: boolean; onSaved: () => void; onPendingChange: (threadId: string, pending: boolean) => void
}) {
  const { session } = useAuth()
  const userId = session!.user.id
  const navigate = useNavigate()
  const completed = useRef(history)
  const [recoveredQuestion] = useState<ChatMessage | null>(() => recovered ? { id: recovered.id, role: 'user', parts: [{ type: 'text', text: recovered.text }] } : null)
  const pending = useRef<ChatMessage | null>(recoveredQuestion)
  const started = useRef(false)
  const bottom = useRef<HTMLDivElement>(null)
  const [failure, setFailure] = useState<string | null>(recovered ? 'The page was reloaded before this reply was confirmed. Retry your question.' : null)
  const [progress, setProgress] = useState('Analyzing question…')
  const [transport] = useState(() => new DefaultChatTransport<ChatMessage>({
    api: `${env.apiBaseUrl}/chat/stream`, fetch: streamFetch,
    prepareSendMessagesRequest: ({ messages }) => ({ body: { threadId, messages: [messages.findLast((message) => message.role === 'user')] } }),
  }))
  const { messages, setMessages, sendMessage, clearError, stop, status } = useChat<ChatMessage>({
    id: threadId, messages: recoveredQuestion ? [...history, recoveredQuestion] : history, transport,
    onError: (error) => setFailure(chatError(error)),
    onData: (part) => {
      if (part.type === 'data-status') {
        const labels: Record<string, string> = { analyzing: 'Analyzing question…', searching: 'Searching filings…', reading: 'Reading source passages…', calculating: 'Checking calculations…', verifying: 'Verifying source support…', repairing: 'Revising unsupported claims…' }
        setProgress(labels[part.data.stage] ?? 'Working…')
      }
    },
    onFinish: ({ messages: finished, isAbort, isDisconnect, isError, finishReason }) => {
      if (!isAbort && !isDisconnect && !isError && finishReason === 'stop') {
        clearPending(userId, threadId)
        completed.current = finished; pending.current = null; setFailure(null); onSaved()
      } else setFailure((current) => current ?? 'Reply interrupted. Retry the same question to recover or finish the turn.')
    },
  })
  const busy = status === 'submitted' || status === 'streaming'
  useEffect(() => { onPendingChange(threadId, busy || failure !== null) }, [threadId, busy, failure, onPendingChange])

  async function send(text: string, id = crypto.randomUUID()) {
    savePending(userId, threadId, { id, text })
    onPendingChange(threadId, true)
    const question: ChatMessage = { id, role: 'user', parts: [{ type: 'text', text }] }
    pending.current = question
    setFailure(null)
    setProgress('Analyzing question…')
    await sendMessage(question)
  }

  useEffect(() => {
    let active = true
    // Defer past StrictMode's rehearsal so it cannot cancel the initial send.
    queueMicrotask(() => {
      if (!active || started.current || !initial) return
      started.current = true
      onPendingChange(threadId, true)
      navigate(`/chats/${threadId}`, { replace: true, state: null })
      const question: ChatMessage = { id: initial.id, role: 'user', parts: [{ type: 'text', text: initial.text }] }
      pending.current = question
      void sendMessage(question)
    })
    return () => { active = false }
  }, [initial, navigate, threadId, sendMessage, onPendingChange])

  // Navigation retains busy sessions; only leaving the workspace or Stop cancels.
  useEffect(() => () => { void stop() }, [stop])

  useEffect(() => { if (active) bottom.current?.scrollIntoView({ block: 'end' }) }, [messages, status, active])

  async function retry() {
    if (!pending.current || busy) return
    setMessages(completed.current); clearError(); setFailure(null)
    setProgress('Analyzing question…')
    await sendMessage(pending.current)
  }

  return <div className="mx-auto flex h-full max-w-3xl flex-col px-4 py-6 sm:px-6">
    <header className="mb-4 border-b pb-4"><h1 className="font-semibold">Conversation</h1><p className="text-xs text-muted-foreground">Private to your account</p></header>
    <div className="min-h-0 flex-1 overflow-y-auto pb-6">
      {!messages.length && <p className="py-8 text-muted-foreground">Send a question to start this conversation.</p>}
      <MessageList messages={messages} provisional={busy || failure !== null} />
      <div ref={bottom} />
    </div>
    <div aria-live="polite" className="mb-3 text-sm">
      {busy && <BusyStatus progress={progress} />}
      {failure && <div className="space-y-2"><p role="alert" className="text-destructive">{failure}</p><Button variant="outline" disabled={busy} onClick={() => void retry()}>Retry question</Button></div>}
    </div>
    <MessageComposer onSend={send} busy={busy} blocked={failure !== null} onStop={() => {
      setFailure('Reply stopped. Retry the same question to recover or finish the turn.')
      void stop()
    }} />
  </div>
}
