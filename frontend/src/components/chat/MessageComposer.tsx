import { useRef, useState, type SubmitEvent } from 'react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { chatError } from '@/lib/chats'

export default function MessageComposer({ busy = false, blocked = false, onSend, onStop }: {
  busy?: boolean; blocked?: boolean; onSend: (text: string) => Promise<void>; onStop?: () => void
}) {
  const [text, setText] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const sending = useRef(false)

  async function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!text.trim() || busy || blocked || sending.current) return
    sending.current = true
    setSubmitting(true)
    setError(null)
    try { await onSend(text.trim()); setText('') }
    catch (cause) { setError(chatError(cause)) }
    finally { sending.current = false; setSubmitting(false) }
  }

  return (
    <form onSubmit={(event) => void submit(event)} className="space-y-3" aria-busy={busy || submitting}>
      <label htmlFor="question" className="sr-only">Your question</label>
      <Textarea id="question" value={text} onChange={(event) => setText(event.target.value)} placeholder="Ask a question about SEC filings…"
        maxLength={16000} rows={3} disabled={busy || submitting || blocked} className="resize-none" />
      <div className="flex items-center justify-between gap-4">
        <p className="text-xs text-muted-foreground">Answers use retrieved filings. Check the cited passages and any evidence gaps.</p>
        {busy && onStop ? <Button type="button" variant="outline" onClick={onStop}>Stop reply</Button>
          : <Button type="submit" disabled={submitting || blocked || !text.trim()}>{submitting ? 'Sending…' : 'Send'}</Button>}
      </div>
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
    </form>
  )
}
