import { env } from '@/lib/env'
import { supabase } from '@/lib/supabase'

export class ApiError extends Error {
  readonly status: number | null
  readonly isNetworkError: boolean

  constructor(message: string, status: number | null = null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.isNetworkError = status === null
  }
}

async function sessionHeaders(): Promise<Headers> {
  const { data, error } = await supabase.auth.getSession()
  if (error) throw new ApiError('Your session could not be restored. Sign in again.', 401)
  const headers = new Headers()
  if (data.session) headers.set('Authorization', `Bearer ${data.session.access_token}`)
  return headers
}

export async function request<T>(method: string, path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  const headers = await sessionHeaders()
  headers.set('Accept', 'application/json')
  if (body !== undefined) headers.set('Content-Type', 'application/json')
  const timeout = AbortSignal.timeout(15_000)
  const combinedSignal = signal ? AbortSignal.any([signal, timeout]) : timeout
  let response: Response
  try {
    response = await fetch(`${env.apiBaseUrl}${path}`, {
      method, headers, signal: combinedSignal,
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    if (signal?.aborted) throw signal.reason
    throw new ApiError(timeout.aborted
      ? 'The request timed out. Try again.'
      : 'Cannot reach the server. Check your connection and try again.')
  }
  if (!response.ok) {
    throw new ApiError(`The server returned HTTP ${response.status}.`, response.status)
  }
  if (response.status === 204) return undefined as T
  try {
    return await response.json() as T
  } catch {
    throw new ApiError('The server returned an unreadable response.', response.status)
  }
}

// Streams use the SDK's abort signal, without the short JSON-request timeout.
export async function streamFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const headers = new Headers(init?.headers)
  for (const [name, value] of await sessionHeaders()) headers.set(name, value)
  let response: Response
  try {
    response = await fetch(input, { ...init, headers })
  } catch (cause) {
    if (init?.signal?.aborted) throw cause
    throw new ApiError('Cannot reach the server. Check your connection and retry.')
  }
  if (!response.ok) throw new ApiError(`The server returned HTTP ${response.status}.`, response.status)
  return response
}
