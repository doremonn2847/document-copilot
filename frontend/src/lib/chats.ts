import type { UIMessage } from 'ai'
import { api } from '@/lib/api'
import { ApiError } from '@/lib/http'

export type Thread = { id: string; title: string; created_at: string; updated_at: string }
export type FirstMessage = { id: string; text: string }

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

export function parseThread(value: unknown): Thread {
  if (!record(value) || typeof value.id !== 'string' || typeof value.title !== 'string'
    || typeof value.created_at !== 'string' || typeof value.updated_at !== 'string') {
    throw new Error('The server returned an invalid conversation.')
  }
  return { id: value.id, title: value.title, created_at: value.created_at, updated_at: value.updated_at }
}

export async function threadPage(offset: number, signal?: AbortSignal): Promise<Thread[]> {
  const data = await api.get<unknown>(`/chat/threads?limit=50&offset=${offset}`, signal)
  if (!Array.isArray(data)) throw new Error('The server returned an invalid conversation list.')
  return data.map(parseThread)
}

export async function messageHistory(threadId: string, signal: AbortSignal): Promise<UIMessage[]> {
  const messages: UIMessage[] = []
  for (let offset = 0; ; offset += 200) {
    const page = await api.get<unknown>(`/chat/threads/${encodeURIComponent(threadId)}/messages?limit=200&offset=${offset}`, signal)
    if (!Array.isArray(page)) throw new Error('The server returned invalid message history.')
    for (const value of page) {
      if (!record(value) || typeof value.id !== 'string' || typeof value.content !== 'string'
        || (value.role !== 'USER' && value.role !== 'ASSISTANT' && value.role !== 'SYSTEM')) {
        throw new Error('The server returned an invalid message.')
      }
      messages.push({ id: value.id, role: value.role === 'USER' ? 'user' : value.role === 'ASSISTANT' ? 'assistant' : 'system',
        parts: [{ type: 'text', text: value.content, state: 'done' }] })
    }
    if (page.length < 200) return messages
  }
}

export function firstMessage(value: unknown): FirstMessage | null {
  if (!record(value) || !record(value.firstMessage)) return null
  const item = value.firstMessage
  return typeof item.id === 'string' && typeof item.text === 'string' ? { id: item.id, text: item.text } : null
}

export function chatError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return 'Your session expired. Sign in again.'
    if (error.status === 403) return 'You do not have access to this conversation.'
    if (error.status === 404) return 'This conversation could not be found.'
    if (error.status === 409) return 'A reply is already in progress, or this message ID was reused. Wait a moment and retry.'
    if (error.isNetworkError) return error.message
  }
  return 'The request could not be completed. Check your connection and try again.'
}
