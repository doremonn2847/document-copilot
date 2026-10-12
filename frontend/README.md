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
- `/`: the approved-user workspace placeholder; chat is not implemented yet.

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
