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
export type ChatMessage = UIMessage<unknown, { citation: Citation; status: { stage: string }; answer: Answer }>

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
