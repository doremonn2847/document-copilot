function required(name: string): string {
  const value: unknown = import.meta.env[name]
  if (typeof value !== 'string' || !value.trim()) {
    throw new Error(`Missing frontend configuration: ${name}`)
  }
  return value.trim()
}

function httpUrl(name: string): string {
  const value = required(name)
  let url: URL
  try {
    url = new URL(value)
  } catch {
    throw new Error(`Invalid frontend configuration: ${name} must be an HTTP(S) URL`)
  }
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.search || url.hash) {
    throw new Error(`Invalid frontend configuration: ${name} must be an HTTP(S) URL without credentials, query, or fragment`)
  }
  return value.replace(/\/+$/, '')
}

const supabaseAnonKey = required('VITE_SUPABASE_ANON_KEY')
if (supabaseAnonKey.startsWith('sb_secret_')) {
  throw new Error('VITE_SUPABASE_ANON_KEY must be a public anon or publishable key')
}
// Legacy Supabase keys are JWTs; a service-role key must never enter the browser.
if (supabaseAnonKey.split('.').length === 3) {
  let role: unknown
  try {
    const payload = supabaseAnonKey.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')
    role = (JSON.parse(atob(payload)) as { role?: unknown }).role
  } catch {
    throw new Error('VITE_SUPABASE_ANON_KEY contains an invalid legacy key')
  }
  if (role !== 'anon') {
    throw new Error('VITE_SUPABASE_ANON_KEY must be a public anon or publishable key')
  }
}

export const env = Object.freeze({
  apiBaseUrl: httpUrl('VITE_API_BASE_URL'),
  supabaseUrl: httpUrl('VITE_SUPABASE_URL'),
  supabaseAnonKey,
})
