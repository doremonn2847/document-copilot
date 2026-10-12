# Agent Instructions

This file is the source of truth for any coding agent (Claude Code, Cursor, Codex, etc.) working in this repo. Read it before touching code.

## Stack

- **Backend:** Python + FastAPI
- **Frontend:** Vite + React SPA + TypeScript
- **Database:** Supabase Postgres (users, chats, source documents, chunks)
- **Migrations:** SQLAlchemy models + Alembic from the backend
- **Retrieval:** Supabase `pgvector` + Postgres full-text search
- **Auth:** Supabase Auth
- **Hosting:** Railway (backend service + frontend service)
- **LLM + embeddings:** OpenAI

Stack is locked unless explicitly changed. Don't propose alternatives without a stated reason.

## Repo layout

```text
document-copilot/
├── AGENTS.md           # this file
├── README.md
├── data/               # local corpus + download script (payloads gitignored)
├── docs/               # specs, briefs, design notes
├── backend/            # FastAPI service (see backend/AGENTS.md)
└── frontend/           # React SPA (see frontend/AGENTS.md)
```

## Owner involvement and learning

The owner is building this project while learning from the tutorial. Act as a
teacher and technical guide. Before each implementation task, decide whether
hands-on owner involvement is needed to understand the structure and steer the
project. State **Owner involvement: opt in / opt out**, with a brief reason.

- **Opt out** for routine scaffolding, repetitive wiring, boilerplate, styling,
  and mechanical changes that add little understanding. Implement and verify
  these autonomously within the authorized scope; briefly explain the result
  and where it fits. A large amount of routine code is not a reason to require
  the owner to type it by hand.
- **Opt in** for work that introduces an important architectural concept or
  decision: data ownership and authorization, API contracts, streaming and
  persistence behavior, retrieval/chunking, grounding and citation validation,
  or consequential schema and deployment choices. Explain the relevant flow,
  recommendation, and tradeoffs before implementing the consequential part.
  Identify one small, concrete decision, coding exercise, or review for the
  owner that helps them understand and control that behavior.

For opt-in work, wait for the owner's decision or exercise result before
implementing the dependent part. Continue independent routine preparation when
useful. Review owner-written code and explain corrections. Do not hand off a
whole subsystem or make the owner reproduce boilerplate merely to participate.
For mixed tasks, involve the owner in the meaningful part and automate the rest.

Judge by learning value and consequences, not task size alone. Do not assume
that earlier permission to implement a feature waives this involvement check.
If the owner explicitly asks the agent to handle the work entirely, respect that
instruction, implement it, and give a concise explanation of the key decisions.
Keep checklist completion tied to verified behavior; distinguish implemented
work from owner decisions and manual checks still pending.

## Dependency policy

**Default: write it yourself. Reach for a library only when the alternative would be non-trivial, error-prone, or reinvention of a standard.** Every dependency is a liability — bundle size, supply-chain risk, future upgrade work.

OK to depend on:

- Things that are genuinely hard to get right (HTTP clients, ASGI servers, SQL drivers, parsers, LLM SDKs, ORM, migrations, auth SDKs).
- The declared stack (FastAPI, React, Vite, Supabase clients, OpenAI SDK, etc.).

Not OK:

- Helper libraries that wrap 5–20 lines of stdlib or platform APIs.
- Frameworks where a function would do.
- "Nicer API" layers on top of an already-present dependency.

Before adding a runtime dep, answer in the commit message:

1. What exactly does it do that we can't write in <30 lines of clear code?
2. How often does it get used?
3. What's its maintenance / transitive-dep footprint?

Per-stack specifics live in `backend/AGENTS.md` and `frontend/AGENTS.md`.

## Configuration

A single settings module is the source of truth for environment per service (`backend/app/config.py`, `frontend/lib/env.ts`). Do not call `os.getenv` / read `process.env` directly in app code. Do not call `load_dotenv` anywhere. If a third-party SDK reads env vars directly, mirror them in the settings module — don't sprinkle `setdefault` elsewhere.

Fail fast on startup if required config is missing. No silent fallbacks that hide real config errors.

## Code style (universal)

- **Small, obvious functions.** A 15-line function with clear names beats a three-class abstraction.
- **No premature abstraction.** Three similar lines is better than a badly-named base class. Extract when there's a third caller, not a hypothetical one.
- **No error handling for cases that can't happen.** Trust internal callers and framework guarantees. Validate only at boundaries: HTTP input, external APIs, DB writes, untrusted parsing.
- **No backwards-compat shims** unless explicitly asked for.
- **No feature flags** added speculatively.
- **Comments:** explain *why* when non-obvious, never *what*. Remove stale TODOs.
- **Keep files focused.** Prefer small modules.
