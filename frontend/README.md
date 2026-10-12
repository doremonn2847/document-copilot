# Document Copilot frontend

From `frontend/`:

```powershell
pnpm install --frozen-lockfile
pnpm dev
```

Open the local URL printed by Vite (normally http://localhost:5173).

Verify changes with `pnpm exec tsc -b`, `pnpm lint`, and `pnpm build`.
`pnpm preview` serves the production build locally.

Routes live in `src/App.tsx`, pages in `src/pages/`, and theme tokens in
`src/index.css`. Use `@/` for imports from `src/`.

Add UI primitives with `pnpm dlx shadcn@latest add <name>`.
Copy `.env.example` to `.env` and fill in the public Supabase URL and anon key
(a publishable key also works). `src/lib/env.ts` validates configuration at startup;
`src/lib/supabase.ts` exports the shared browser client. Restart Vite after editing
`.env`. Never include a service-role key or database password in frontend settings.

## Sign-up and approval

Run FastAPI on port 8001 alongside Vite. Use `http://localhost:5173` so the
browser origin matches the backend CORS configuration.

- `/signup`: register with email/password, then check your confirmation email.
- `/login`: sign in after confirming your email.
- `/pending-approval`: signed-in users without an approved profile wait here.
- `/`: redirects approved users to `/chats`.
- `/chats`: unsaved new-chat draft and private conversation sidebar.
- `/chats/:threadId`: saved history, streamed test replies, Stop and Retry.

In Supabase, enable new-user signups and email confirmation, set the Site URL
to `http://localhost:5173`, and allow `http://localhost:5173/auth/callback`
as a redirect URL. Use the deployed URLs in production.

After reviewing an account, approve its Auth UUID from `backend/`:

```powershell
uv run python -m app.database.approve_user <user-uuid>
```

The user can select **Check again** without signing out. Refreshing the page
restores the session and checks approval again. Sign out clears this browser's
session. API requests use `src/lib/api.ts` to attach the bearer token.

Manual verification: create and confirm an account → sign in → see pending
approval → approve the account → Check again → see the workspace → reload →
sign out. Also verify an existing approved account, a wrong password, a failed
confirmation link, and the retry screen with FastAPI stopped.

## Chat verification

New chat creates no database row until the first send. Completed question/reply
pairs are saved together; interrupted text remains provisional. Retry keeps the
same question ID so a reply committed just before a connection loss is replayed
without duplication. Leaving a conversation stops its active request. Empty
threads created by failed first sends remain available for another attempt.

Submitted questions and their retry IDs remain in account-scoped tab session
storage until completion. Reloading an interrupted conversation restores the
question with an explicit Retry button; saved history clears already-completed
recovery records. This recovery lasts for the tab session, not across devices.
The first send stores a recovery record before creating the thread. An immediate
reload on `/chats` shows Retry question; retries reuse the same thread ID and
cannot create duplicate threads. Also test this with browser network throttling.

With both services running, send a question, watch the test reply stream, reload,
and reopen the conversation from the sidebar. Stop a second reply and retry it;
reload to check there is one completed pair. Check another approved account cannot
open the first account's thread URL. The developer confirmed reload/retry recovery,
including immediate reload after first send. Explicit Stop and cross-account
browser checks remain pending.
