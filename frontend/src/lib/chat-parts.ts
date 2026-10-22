import type { UIMessage } from 'ai'

export type Citation = {
  index: number; chunk_id: string; document_id: string; chunk_index: number
  excerpt: string; ticker: string; form: string; source_url: string
  filing_date: string; report_date: string | null; corpus_year: number | null
  fiscal_year: number | null; page: string | null; section: string | null
  source_kind?: 'original_table_context' | 'indexed_chunk'
}
export type AnswerBlock =
  | { kind: 'claim'; claim_kind: 'fact' | 'calculation' | 'interpretation'; label: string | null; text: string; citations: number[] }
  | { kind: 'gap'; label: string | null; text: string }
  | { kind: 'notice'; text: string }
export type Answer = { blocks: AnswerBlock[] }
export const FEEDBACK_REASONS = {
  wrong_fact: 'Wrong fact', wrong_citation: 'Wrong citation or page', missing_information: 'Missing information',
  should_have_answered: 'Should have answered', too_slow: 'Too slow', other: 'Other',
} as const
export type FeedbackReason = keyof typeof FEEDBACK_REASONS
export type Feedback = { rating: 'up' | 'down'; reason: FeedbackReason | null; comment: string | null }
export type ChatMessage = UIMessage<{ feedback?: Feedback | null }, { citation: Citation; status: { stage: string }; answer: Answer }>

export function parseFeedback(value: unknown): Feedback | null {
  if (typeof value !== 'object' || value === null) return null
  const f = value as Record<string, unknown>
  if (f.rating !== 'up' && f.rating !== 'down') return null
  const reason = typeof f.reason === 'string' && f.reason in FEEDBACK_REASONS ? f.reason as FeedbackReason : null
  return { rating: f.rating, reason, comment: typeof f.comment === 'string' ? f.comment : null }
}

function parseBlock(value: unknown): AnswerBlock {
  if (typeof value !== 'object' || value === null) throw new Error('Invalid answer block.')
  const block = value as Record<string, unknown>
  const label = block.label ?? null
  if (typeof block.text !== 'string' || (label !== null && typeof label !== 'string')) throw new Error('Invalid answer block.')
  if (block.kind === 'notice') return { kind: 'notice', text: block.text }
  if (block.kind === 'gap') return { kind: 'gap', label, text: block.text }
  if (block.kind === 'claim' && (block.claim_kind === 'fact' || block.claim_kind === 'calculation' || block.claim_kind === 'interpretation')
    && Array.isArray(block.citations) && block.citations.every(Number.isInteger)) {
    return { kind: 'claim', claim_kind: block.claim_kind, label, text: block.text, citations: block.citations as number[] }
  }
  throw new Error('Invalid answer block.')
}

export function parseAnswer(value: unknown): Answer {
  if (typeof value !== 'object' || value === null || !Array.isArray((value as { blocks?: unknown }).blocks)) {
    throw new Error('Invalid structured answer.')
  }
  return { blocks: (value as { blocks: unknown[] }).blocks.map(parseBlock) }
}

export function parseCitation(value: unknown): Citation {
  if (typeof value !== 'object' || value === null) throw new Error('Invalid source metadata.')
  const data = value as Record<string, unknown>
  if (data.source_kind !== undefined && data.source_kind !== 'original_table_context' && data.source_kind !== 'indexed_chunk') throw new Error('Invalid source kind.')
  for (const key of ['chunk_id', 'document_id', 'excerpt', 'ticker', 'form', 'source_url', 'filing_date']) {
    if (typeof data[key] !== 'string') throw new Error('Invalid source metadata.')
  }
  for (const key of ['index', 'chunk_index']) {
    if (!Number.isInteger(data[key])) throw new Error('Invalid source index.')
  }
  for (const key of ['corpus_year', 'fiscal_year']) {
    if (data[key] !== null && !Number.isInteger(data[key])) throw new Error('Invalid source year.')
  }
  for (const key of ['report_date', 'page', 'section']) {
    if (data[key] !== null && typeof data[key] !== 'string') throw new Error('Invalid source location.')
  }
  return data as Citation
}

export function secLink(source: string): string | undefined {
  try {
    const url = new URL(source)
    return url.protocol === 'https:' && (url.hostname === 'www.sec.gov' || url.hostname === 'sec.gov') && !url.username && !url.password ? url.href : undefined
  } catch { return undefined }
}

export function pageLabel(page: string | null): string {
  return page ? `${page.includes('–') ? 'pages' : 'page'} ${page}` : 'page unverified'
}

const CLAIM_PREFIX = { fact: '', calculation: 'Calculation: ', interpretation: 'Interpretation: ' }

// Plain text for pasting into notes and memos: the answer in the order shown,
// then each source with its quoted passage and SEC link.
export function answerText(blocks: AnswerBlock[], citations: Citation[]): string {
  const ordered = [...blocks.filter((b) => b.kind === 'notice'), ...blocks.filter((b) => b.kind === 'claim'), ...blocks.filter((b) => b.kind === 'gap')]
  const lines = ordered.map((b) => {
    if (b.kind === 'notice') return `Note: ${b.text}`
    const label = b.label ? `${b.label}: ` : ''
    if (b.kind === 'gap') return label + b.text
    return `${CLAIM_PREFIX[b.claim_kind]}${label}${b.text} ${b.citations.map((n) => `[${n}]`).join(' ')}`
  })
  const sources = [...citations].sort((a, b) => a.index - b.index).map((c) => {
    const link = secLink(c.source_url)
    return [
      `[${c.index}] ${c.ticker} ${c.form}, corpus ${c.corpus_year ?? 'unknown'}, ${c.fiscal_year ? `FY ${c.fiscal_year}` : 'fiscal year unverified'}, filed ${c.filing_date}, ${pageLabel(c.page)}${c.section ? `, ${c.section}` : ''}`,
      `    "${c.excerpt.replace(/\n/g, '\n     ')}"`,
      ...(link ? [`    ${link}`] : []),
    ].join('\n')
  })
  return [...lines, ...(sources.length ? ['Sources', ...sources] : [])].join('\n\n')
}
