# Frontend setup

This project uses a Vite + React SPA because the frontend is an internal tool that mainly needs fast iteration, authenticated app flows, and a clean connection to the FastAPI backend. We do not need the extra server-rendering, SEO, or full-stack routing features that Next.js is optimized for.

## Init (from empty `frontend/`)

```bash
cd frontend
pnpm create vite . --template react-ts
pnpm install
pnpm add react-router-dom @supabase/supabase-js
pnpm add -D tailwindcss @tailwindcss/vite
pnpm dlx shadcn@latest init
```

## Run

```bash
cd frontend
pnpm install
pnpm dev
```

## Check

```bash
pnpm tsc --noEmit
pnpm lint
```

## Conversation navigation

The authenticated workspace retains the visible conversation and conversations
with an active reply or a pending retry. Navigating to another chat hides the
previous view without stopping its stream. A completed background conversation
is released from memory and reopened from persisted history. Retryable failures
retain their actual error while navigating within the workspace.

Stop still aborts the selected conversation. Logout, a change of account, leaving
the workspace, refreshing, or closing the page releases sessions and interrupts
unfinished requests. Refresh uses the existing pending-question recovery; this
is not a backend background-job system. Hidden sessions cannot scroll the visible
conversation. Each thread keeps its own messages, progress, failure and citations.

2026-10-21: TypeScript, lint and production build checked. Browser confirmation
is pending: start a reply, switch to another chat, return during generation, then
verify its saved answer after completion. Also check Stop/retry, a background
failure, reload recovery and logout. No paid model calls were made for this change.
