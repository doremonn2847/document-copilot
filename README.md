# Document Copilot

An internal AI chatbot that lets analysts query a corpus of documents in plain English and get sourced, citable answers.

Referenced, implemented, and extended an existing tutorial of the [**Build a Complete**](https://youtube.com/@daveebbelaar) series — episode 1.

## The client

**Driftwood Capital** — fictional independent investment research firm. Their analysts spend half their week reading 10-Ks and 10-Qs before they can produce any original analysis. Document Copilot eats that intake work so they can skip straight to insight.

Full brief: [docs/client-brief.md](docs/client-brief.md)

## Stack

| Layer              | Choice                                               |
| ------------------ | ---------------------------------------------------- |
| Backend            | Python + FastAPI                                     |
| Frontend           | Vite + React SPA + TypeScript                        |
| Database           | Supabase Postgres (users, chats, documents, chunks)  |
| Migrations         | SQLAlchemy models + Alembic                          |
| Retrieval          | Supabase `pgvector` + Postgres full-text search      |
| Auth               | Supabase Auth (email only)                           |
| Hosting            | Railway                                              |
| LLM + embeddings   | OpenAI                                               |

## Repo layout

```text
document-copilot/
├── AGENTS.md           # agent instructions (read first)
├── README.md           # this file
├── data/               # local corpus + download script (payloads gitignored)
├── docs/
│   └── client-brief.md # the client one-pager
├── backend/            # FastAPI service
└── frontend/           # React SPA (Vite)
```

## Prerequisites

Install these before setting up `backend/` or `frontend/`:

| Tool | Version | Used for | Install |
| ---- | ------- | -------- | ------- |
| [Python](https://www.python.org/downloads/) | 3.12+ | Backend runtime | OS package manager or python.org |
| [uv](https://docs.astral.sh/uv/getting-started/installation/) | latest | Backend deps + `data/download.py` | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| [Node.js](https://nodejs.org/) | 22.12+ (supported LTS) | Frontend toolchain | nodejs.org or `nvm install --lts` |
| [pnpm](https://pnpm.io/installation) | latest | Frontend package manager | `corepack enable && corepack prepare pnpm@latest --activate` |

You also need accounts/keys for external services once the app is wired up. Start with [docs/guides/supabase-setup.md](docs/guides/supabase-setup.md) (account + project), then create an [OpenAI API key](https://platform.openai.com/api-keys) when the LLM layer is wired up.

## Running locally

Copy each service's `.env.example` to `.env` only if it does not already exist,
then configure credentials privately. Do not overwrite an existing environment.
Run the services in separate terminals:

```powershell
# Terminal 1, from backend/
uv sync --locked
uv run --locked python -m uvicorn app.main:app --reload --port 8001

# Terminal 2, from frontend/
pnpm install --frozen-lockfile
pnpm dev
```

Open http://localhost:5173. New users confirm their email, then require approval
with `uv run --locked python -m app.database.approve_user <auth-user-uuid>` from
`backend/`. The app uses real retrieval and grounded answers, not stub replies.

Current scope: the owner accepted a five-company, 25-filing 10-K pilot. Phases
6–8 were accepted with documented answer-quality limitations. Hosted acceptance
and the owner-timed stand-in pilot are separate gates.

- [AI handoff](docs/AI_HANDOFF.md) — current architecture and accepted decisions
- [Delivery status](docs/operations/delivery-status.md) — verified deployment steps and remaining owner/live checks
- [Operations runbook](docs/operations/runbook.md)
- [Stand-in pilot](docs/pilot/pilot-plan.md) — six matched task pairs and measurement rules

Setup guides:

- [Supabase](docs/guides/supabase-setup.md) — account, hosted project (dashboard or CLI)
- [Backend](docs/guides/backend-setup.md)
- [Frontend](docs/guides/frontend-setup.md)

## Sample SEC data

Use the standalone downloader to fetch a small local 10-K sample from SEC EDGAR.
Edit the params at the top of `data/download.py`, especially `USER_AGENT`, then run:

```bash
uv run data/download.py
```

The downloader targets corpus years 2021–2025 for AAPL, MSFT, NVDA, AMZN, and GOOGL
under `data/downloads/` and writes a `manifest.json`. Deployment reuses the
already-indexed corpus; do not download or re-embed it just to deploy.
Downloaded files are gitignored; the `data/` folder itself stays in git for the script and notes.
