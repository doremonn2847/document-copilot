import { useState } from 'react'
import { ThumbsDown, ThumbsUp } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { FEEDBACK_REASONS, type Feedback, type FeedbackReason } from '@/lib/chat-parts'
import { clearFeedback, saveFeedback } from '@/lib/chats'

const REASONS = Object.keys(FEEDBACK_REASONS) as FeedbackReason[]

// Thumbs up saves at once; thumbs down asks what went wrong. Clicking the
// active thumb again removes the rating.
export default function AnswerFeedback({ messageId, initial }: { messageId: string; initial: Feedback | null }) {
  const [saved, setSaved] = useState(initial)
  const [asking, setAsking] = useState(false)
  const [reason, setReason] = useState<FeedbackReason | null>(null)
  const [comment, setComment] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function run(action: () => Promise<Feedback | null>) {
    setBusy(true)
    setError(null)
    try {
      setSaved(await action())
      setAsking(false)
    } catch {
      setError('Feedback could not be saved. Try again.')
    } finally {
      setBusy(false)
    }
  }
  const clear = () => run(async () => { await clearFeedback(messageId); return null })
  const up = saved?.rating === 'up'
  const down = saved?.rating === 'down' || asking

  return <div className="flex flex-wrap items-center gap-1">
    <Button type="button" variant="ghost" size="icon-sm" disabled={busy} aria-pressed={up} aria-label="Helpful answer"
      className={up ? 'text-primary' : 'text-muted-foreground'}
      onClick={() => void (up ? clear() : run(() => saveFeedback(messageId, { rating: 'up', reason: null, comment: null })))}>
      <ThumbsUp aria-hidden="true" />
    </Button>
    <Button type="button" variant="ghost" size="icon-sm" disabled={busy} aria-pressed={down} aria-label="Report a problem with this answer"
      className={down ? 'text-destructive' : 'text-muted-foreground'}
      onClick={() => { if (saved?.rating === 'down') void clear(); else setAsking(!asking) }}>
      <ThumbsDown aria-hidden="true" />
    </Button>
    {saved && !asking && <span className="text-xs text-muted-foreground" aria-live="polite">
      {saved.rating === 'up' ? 'Thanks for the feedback' : `Reported${saved.reason ? `: ${FEEDBACK_REASONS[saved.reason]}` : ''}`}
    </span>}
    {error && <span role="alert" className="text-xs text-destructive">{error}</span>}
    {asking && <form className="mt-2 w-full space-y-2 rounded-md border p-3" onSubmit={(event) => {
      event.preventDefault()
      void run(() => saveFeedback(messageId, { rating: 'down', reason, comment: comment.trim() || null }))
    }}>
      <fieldset className="flex flex-wrap gap-1">
        <legend className="mb-1 text-sm font-medium">What went wrong?</legend>
        {REASONS.map((key) => <Button key={key} type="button" size="xs" variant={reason === key ? 'default' : 'outline'}
          aria-pressed={reason === key} onClick={() => setReason(reason === key ? null : key)}>
          {FEEDBACK_REASONS[key]}
        </Button>)}
      </fieldset>
      <Textarea value={comment} maxLength={500} onChange={(event) => setComment(event.target.value)} aria-label="Feedback comment"
        placeholder="Optional: what was wrong or missing, for example the correct figure or page" />
      <div className="flex gap-2">
        <Button type="submit" size="sm" disabled={busy}>Send feedback</Button>
        <Button type="button" size="sm" variant="ghost" onClick={() => setAsking(false)}>Cancel</Button>
      </div>
    </form>}
  </div>
}
