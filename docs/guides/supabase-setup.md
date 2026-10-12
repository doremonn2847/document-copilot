# Supabase setup

We use Supabase for **Postgres** (users, chats, source documents, chunks, embeddings, and citations) and **Auth** (email sign-in only). You need one hosted Supabase project before wiring up `backend/` and `frontend/`.

## 1. Create an account

1. Go to [supabase.com](https://supabase.com) and sign up (GitHub or email).
2. Confirm your email if prompted.
3. You land in the [dashboard](https://supabase.com/dashboard). The free tier is enough for local development.

## 2. Create a project

1. Open [New project](https://supabase.com/dashboard/new).
2. Pick your organization (a personal org is created automatically on first signup).
3. Set a **project name** (e.g. `Document Copilot`).
4. Choose a **database password** — save it somewhere safe; you need it for direct DB access and `supabase link`.
5. Pick a **region** close to you.
6. Click **Create new project** and wait until status is healthy (~1–2 minutes).

## 3. Collect credentials

You need these values in backend and frontend env config (exact variable names will live in each service's settings module once the app is built).

| Value | Where to find it | Used by |
| ----- | ---------------- | ------- |
| **Project URL** | Dashboard → **Project Settings** → **API** → Project URL | Frontend + backend |
| **anon (public) key** | Same page → `anon` `public` key | Frontend (browser-safe) |
| **service_role (secret) key** | Same page → `service_role` `secret` key | Backend only — never expose to the browser |
| **Project ref** | Dashboard URL `supabase.com/dashboard/project/<ref>` or `supabase projects list` | CLI commands |
| **Direct database connection string** | Dashboard → **Project Settings** → **Database** → Connection string | Alembic migrations and backend DB access |
| **Database password** | What you set at project creation | Direct Postgres connection |

From the CLI you can also print API keys:

```bash
supabase projects api-keys --project-ref <your-project-ref>
```

Keep `service_role` out of git, client bundles, and frontend env files.

## 4. Auth settings (email only)

This app uses email auth only — no Google/SSO.

1. Dashboard → **Authentication** → **Providers**.
2. Leave **Email** enabled.
3. Enable **Allow new users to sign up** in the Auth settings.
4. Keep **Confirm email** enabled. Set the **Site URL** to the frontend URL
   (`http://localhost:5173` for local development) and allow that URL in the
   redirect configuration, including `http://localhost:5173/auth/callback` for
   confirmation links. Use the deployed frontend URL and its `/auth/callback`
   route in production. Open the app using the same hostname as these settings.
5. Registration and email confirmation do not grant app access. A confirmed
   account without a `public.users` profile receives **403** from protected APIs.
6. Review the registration, then approve the user's Auth UUID from `backend/`:

   ```bash
   uv run python -m app.database.approve_user <user-uuid>
   ```

The command only approves active, email-confirmed accounts. Do not add a trigger
that automatically inserts profiles on registration: profiles are the approval
list. Approval is an administrator CLI action, not a public endpoint.

The frontend provides `/signup`, `/login`, `/auth/callback`, and
`/pending-approval`. After sign-in, `/auth/me` determines whether the user can
enter the app. Pending users can check again after manual approval; a server
failure shows a retry screen rather than treating them as approved or pending.
If confirmation emails hit the provider rate limit, configure SMTP before
opening registration to more users.

## 5. Database schema management

Document Copilot uses Alembic from the Python backend to manage database schema. Do not create production tables manually in the Supabase dashboard.

Alembic migrations create and update:

- the `vector` extension for `pgvector`
- source document and chunk tables
- embedding columns
- generated full-text search columns
- HNSW and GIN indexes
- chat and citation tables
- row-level security policies

Use the direct/session database connection string for Alembic. Do not use the transaction pooler connection string for migrations.

From `backend/`:

```bash
uv run alembic upgrade head
```

See [Backend setup](backend-setup.md) for the Alembic workflow.

## Next steps

- [Backend setup](backend-setup.md) — Python service + Supabase client
- [Frontend setup](frontend-setup.md) — React app + `@supabase/supabase-js`
