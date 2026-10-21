# Phase 8 results: answer quality on the client brief

Runs: night of 2026-10-22, production settings (gpt-5.4-mini answering,
gpt-4.1-mini judging, gpt-4o-mini keywords, text-embedding-3-small) through the
capped driver `data/chunks/assistant/capped_question.py`. Per-run artifacts
(`autopilot-p8-*.json`, gitignored) hold searches, judge payloads, requests and
timings. An answer is marked correct only after each claim was read against its
own quotes.

## Credential exposure (task 5)

- Production frontend build (`vite build` to a scratch directory): no OpenAI
  keys, Supabase secret keys, Postgres URLs, service-role JWTs or server
  variable names. The only Supabase key is the public publishable key, which
  `src/lib/env.ts` already rejects if it is a secret or legacy service key.
- 150 local backend logs and run artifacts: no OpenAI keys, Supabase secrets,
  Postgres URLs, bearer tokens or JWTs. Backend code does not log request
  headers, keys or connection strings.
- Not covered: logs of the deployed Railway services (phase 9).
