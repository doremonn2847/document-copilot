import { secLink, type AnswerBlock, type ChatMessage, type Citation } from '@/lib/chat-parts'

type ClaimBlock = Extract<AnswerBlock, { kind: 'claim' }>

function sourceId(messageId: string, index: number) {
  return `source-${messageId}-${index}`
}

// One click opens the cited passage and moves focus to it.
function openSource(messageId: string, index: number) {
  const source = document.getElementById(sourceId(messageId, index))
  if (!(source instanceof HTMLDetailsElement)) return
  source.open = true
  source.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  source.querySelector('summary')?.focus()
}

function CitationButtons({ messageId, numbers }: { messageId: string; numbers: number[] }) {
  return <>{numbers.map((n) => <button key={n} type="button" onClick={() => openSource(messageId, n)}
    className="ml-1 rounded px-1 align-baseline text-xs font-semibold text-primary underline-offset-2 hover:underline focus-visible:outline focus-visible:outline-2"
    aria-label={`Show source ${n}`}>[{n}]</button>)}</>
}

function Claim({ messageId, block }: { messageId: string; block: ClaimBlock }) {
  const kind = block.claim_kind === 'fact' ? null : block.claim_kind === 'calculation' ? 'Calculation' : 'Interpretation'
  return <li className="leading-relaxed">
    {kind && <span className="mr-2 rounded bg-muted px-1.5 py-0.5 text-xs font-semibold">{kind}</span>}
    {block.text}<CitationButtons messageId={messageId} numbers={block.citations} />
  </li>
}

// Comparison facts carry "TICKER / FORM / corpus YEAR" labels; group them by company.
function ClaimGroups({ messageId, claims }: { messageId: string; claims: ClaimBlock[] }) {
  const groups: { company: string | null; claims: ClaimBlock[] }[] = []
  for (const claim of claims) {
    const company = claim.label?.split(' / ')[0] ?? null
    const last = groups[groups.length - 1]
    if (last && last.company === company) last.claims.push(claim)
    else groups.push({ company, claims: [claim] })
  }
  return <>{groups.map((group, i) => <section key={i} className="space-y-2">
    {group.company && <h3 className="text-sm font-semibold">{group.company}</h3>}
    <ul className="space-y-2">{group.claims.map((claim, j) => claim.label
      ? <li key={j} className="leading-relaxed"><span className="mr-2 rounded border px-1.5 py-0.5 text-xs text-muted-foreground">{claim.label.split(' / ').slice(1).join(' · ')}</span>{claim.text}<CitationButtons messageId={messageId} numbers={claim.citations} /></li>
      : <Claim key={j} messageId={messageId} block={claim} />)}</ul>
  </section>)}</>
}

function Blocks({ messageId, blocks }: { messageId: string; blocks: AnswerBlock[] }) {
  const notices = blocks.filter((b) => b.kind === 'notice')
  const claims = blocks.filter((b): b is ClaimBlock => b.kind === 'claim')
  const gaps = blocks.filter((b) => b.kind === 'gap')
  return <div className="space-y-4">
    {notices.map((notice, i) => <p key={i} role="note" className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-950 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-100">{notice.text}</p>)}
    {claims.length > 0 && <ClaimGroups messageId={messageId} claims={claims} />}
    {gaps.length > 0 && <section aria-label="Not established" className="space-y-2">
      <h3 className="text-sm font-semibold text-muted-foreground">Not established</h3>
      <ul className="space-y-2">{gaps.map((gap, i) => <li key={i} className="rounded-md border border-dashed px-3 py-2 text-sm text-muted-foreground">
        {gap.label && <span className="mr-2 font-semibold">{gap.label}</span>}
        {gap.text.replace(/^Not established from the retrieved evidence: /, '')}
      </li>)}</ul>
    </section>}
  </div>
}

function Source({ messageId, citation: c }: { messageId: string; citation: Citation }) {
  const link = secLink(c.source_url)
  return <details id={sourceId(messageId, c.index)} className="rounded border p-2 text-sm">
    <summary className="cursor-pointer rounded focus-visible:outline focus-visible:outline-2">[{c.index}] {c.ticker} {c.form} · corpus {c.corpus_year ?? 'unknown'} · {c.fiscal_year ? `FY ${c.fiscal_year}` : 'fiscal year unverified'}</summary>
    <blockquote className="my-2 whitespace-pre-wrap break-words border-l-2 pl-3">{c.excerpt}</blockquote>
    <p className="text-xs text-muted-foreground">
      Filed {c.filing_date} · {c.page ? `page ${c.page}` : 'page unverified'}{c.section ? ` · ${c.section}` : ''} · {c.source_kind === 'original_table_context' ? 'original table context via ' : ''}chunk {c.chunk_index}
    </p>
    {link && <a href={link} target="_blank" rel="noopener noreferrer" className="underline">Original SEC filing</a>}
  </details>
}

export default function MessageList({ messages, provisional }: { messages: ChatMessage[]; provisional: boolean }) {
  return <div className="space-y-6">{messages.map((message, index) => {
    const answer = message.parts.find((part) => part.type === 'data-answer')
    const citations = message.parts.filter((part) => part.type === 'data-citation').map((part) => part.data)
    const text = message.parts.filter((part) => part.type === 'text').map((part) => part.text).join('')
    const pending = provisional && message.role === 'assistant' && index === messages.length - 1
    return <article key={message.id} className={message.role === 'user' ? 'ml-8 rounded-xl bg-muted p-4' : 'mr-8 p-4'}>
      <p className="mb-2 text-xs font-semibold text-muted-foreground">{message.role === 'user' ? 'You' : 'Document Copilot'}</p>
      {message.role === 'assistant' && answer
        ? <Blocks messageId={message.id} blocks={answer.data.blocks} />
        : <p className="whitespace-pre-wrap break-words">{text}</p>}
      {message.role === 'assistant' && citations.length > 0 && <div className="mt-4 space-y-2 border-t pt-3" aria-label="Sources">
        <p className="text-xs font-semibold">Sources</p>
        {citations.map((citation) => <Source key={citation.index} messageId={message.id} citation={citation} />)}
      </div>}
      {pending && <p className="mt-2 text-xs text-muted-foreground">Provisional reply: not yet saved</p>}
    </article>
  })}</div>
}
