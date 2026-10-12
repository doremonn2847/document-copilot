import { firstMessage, type FirstMessage } from '@/lib/chats'

export const chatDocumentId = crypto.randomUUID()

export type PendingCreation = FirstMessage & { threadId: string }

export function saveCreation(userId: string, question: PendingCreation) {
  sessionStorage.setItem(key(userId, 'new'), JSON.stringify(question))
}

export function readCreation(userId: string): PendingCreation | null {
  const value = sessionStorage.getItem(key(userId, 'new'))
  if (!value) return null
  try {
    const item: unknown = JSON.parse(value)
    if (typeof item !== 'object' || item === null || !('threadId' in item)
      || typeof item.threadId !== 'string' || !/^[0-9a-f-]{36}$/i.test(item.threadId)) return null
    const question = firstMessage({ firstMessage: item })
    return question ? { ...question, threadId: item.threadId } : null
  } catch { return null }
}

export function clearCreation(userId: string) { sessionStorage.removeItem(key(userId, 'new')) }

function key(userId: string, threadId: string) {
  return `document-copilot:pending:${userId}:${threadId}`
}

export function savePending(userId: string, threadId: string, question: FirstMessage) {
  sessionStorage.setItem(key(userId, threadId), JSON.stringify({ firstMessage: question }))
}

export function readPending(userId: string, threadId: string): FirstMessage | null {
  const value = sessionStorage.getItem(key(userId, threadId))
  if (!value) return null
  try { return firstMessage(JSON.parse(value)) } catch { return null }
}

export function clearPending(userId: string, threadId: string) {
  sessionStorage.removeItem(key(userId, threadId))
}

// Match the backend's UUID5(threadId, "user:" + questionId) for exact reconciliation.
export async function savedQuestionId(threadId: string, questionId: string): Promise<string> {
  const namespace = Uint8Array.from(threadId.replaceAll('-', '').match(/../g)!, (byte) => parseInt(byte, 16))
  const name = new TextEncoder().encode(`user:${questionId}`)
  const input = new Uint8Array(namespace.length + name.length)
  input.set(namespace); input.set(name, namespace.length)
  const bytes = new Uint8Array(await crypto.subtle.digest('SHA-1', input)).slice(0, 16)
  bytes[6] = (bytes[6] & 15) | 80
  bytes[8] = (bytes[8] & 63) | 128
  const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('')
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`
}
