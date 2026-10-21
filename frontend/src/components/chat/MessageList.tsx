import { secLink, type ChatMessage } from '@/lib/chat-parts'

export default function MessageList({ messages, provisional }: { messages: ChatMessage[]; provisional: boolean }) {
  return <div className="space-y-6">{messages.map((message, index) => (
    <article key={message.id} className={message.role === 'user' ? 'ml-8 rounded-xl bg-muted p-4' : 'mr-8 p-4'}>
      <p className="mb-2 text-xs font-semibold text-muted-foreground">{message.role === 'user' ? 'You' : 'Document Copilot'}</p>
      <p className="whitespace-pre-wrap break-words">{message.parts.filter((part) => part.type === 'text').map((part) => part.text).join('')}</p>
      {message.role === 'assistant' && message.parts.some((p) => p.type === 'data-citation') && <div className="mt-4 space-y-2 border-t pt-3" aria-label="Sources">
        <p className="text-xs font-semibold">Sources</p>
        {message.parts.filter((p) => p.type === 'data-citation').map(({ data: c }) => <details key={c.index} className="rounded border p-2 text-sm">
          <summary className="cursor-pointer">[{c.index}] {c.ticker} {c.form} · corpus {c.corpus_year ?? 'unknown'} · {c.fiscal_year ? `FY ${c.fiscal_year}` : 'fiscal year unverified'}</summary>
          <blockquote className="my-2 whitespace-pre-wrap break-words border-l-2 pl-3">{c.excerpt}</blockquote>
          <p className="text-xs text-muted-foreground">Filed {c.filing_date} · {c.page ? `page ${c.page}` : 'page unverified'} · {c.source_kind === 'original_table_context' ? 'original table context via ' : ''}chunk {c.chunk_index}</p>
          {secLink(c.source_url) && <a href={secLink(c.source_url)} target="_blank" rel="noopener noreferrer" className="underline">Original SEC filing</a>}
        </details>)}
      </div>}
      {provisional && message.role === 'assistant' && index === messages.length - 1 && <p className="mt-2 text-xs text-muted-foreground">Provisional reply</p>}
    </article>
  ))}</div>
}
