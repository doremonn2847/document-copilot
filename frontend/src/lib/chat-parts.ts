import type { UIMessage } from 'ai'

export type Citation = {
  index: number; chunk_id: string; document_id: string; chunk_index: number
  excerpt: string; ticker: string; form: string; source_url: string
  filing_date: string; report_date: string | null; corpus_year: number | null
  fiscal_year: number | null; page: string | null; section: string | null
  source_kind?: 'original_table_context' | 'indexed_chunk'
}
export type ChatMessage = UIMessage<unknown, { citation: Citation; status: { stage: string } }>

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
