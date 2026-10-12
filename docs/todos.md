# Document Copilot implementation checklist

Build order: backend foundation → database and identity → a thin frontend with
working chat plumbing → ingestion → retrieval → grounded answers → polished
citations → deployment → analyst pilot.

Build both sides in small connected steps. Do not finish the entire backend before
trying it from the browser. Each milestone below has an observable completion gate.
Mark a task complete only after checking its result.

References: [client brief](client-brief.md), [architecture](architecture.md),
[backend setup](guides/backend-setup.md), [frontend setup](guides/frontend-setup.md).

## 0. Starting point

- [x] Install and verify Python, uv, Node.js, and pnpm.
- [x] Copy the tutorial's `Document Copilot Setup` snapshot, including all `AGENTS.md` files.
- [x] Initialize Git and push the setup commit to our GitHub repository.
- [x] Download the initial SEC sample files and manifest into ignored `data/downloads/`.
- [ ] Check the manifest and downloaded files cover the expected 25 filings: AAPL, AMZN, GOOGL, MSFT, and NVDA, fiscal years 2021–2025.
- [ ] Turn the ten example questions in the client brief into an evaluation worksheet: expected companies/years, source passages, figures, and appropriate refusals. Start with a few simple questions and expand as ingestion becomes available.
- [ ] Resolve page citations before choosing the extraction format: preserve actual filing page labels and source locations. HTML line numbers or invented page numbers are not valid substitutes. If reliable pages are unavailable, obtain client agreement on section/anchor citations before considering this requirement satisfied.

**Gate:** The starting scope and evidence needed to demonstrate success are clear.

## 1. Backend foundation

- [ ] Set up the backend environment with uv and add the declared backend dependencies as needed; add pytest and Ruff for development.
- [x] Verify dependency pinning and release-age configuration uses valid uv settings and is actually enforced; commit the generated lockfile.
- [ ] Create the FastAPI entry point and a health endpoint; run it locally with Uvicorn.
- [ ] Add the central Pydantic settings module, a safe `.env.example`, and ignored local environment files. Validate required configuration at startup.
- [ ] Configure explicit development CORS origins and structured logs without credentials or bearer tokens.
- [ ] Add a small backend test foundation and verify the health endpoint and configuration failures.

**Gate:** The backend starts reproducibly, serves a health response, and reports missing configuration clearly.

## 2. Database, migrations, and identity

- [ ] Create the Supabase project and configure email authentication for the internal application.
- [ ] Decide how approved Driftwood users are admitted, using invitations or an approved-email policy enforced server-side. Email verification alone must not admit arbitrary outsiders.
- [ ] Configure the backend Supabase clients and direct/session Postgres connection for Alembic.
- [ ] Define SQLAlchemy models for profiles/users, chat threads, messages, citations, source documents, and document chunks, with foreign keys and ownership fields.
- [ ] Add reviewed Alembic migrations for tables, `pgvector`, embedding dimensions, generated full-text vectors, and HNSW/GIN indexes.
- [ ] Add RLS policies and grants; restrict private conversations to their owners and corpus access to approved authenticated users. Check authorization explicitly in privileged backend operations.
- [ ] Apply migrations to a fresh development database and verify they reproduce the expected schema.
- [ ] Verify Supabase bearer tokens in FastAPI and derive identity from the verified session.
- [ ] Test missing/expired/invalid tokens, unapproved users, and cross-user access using two accounts, including direct database access where permitted.

**Gate:** An approved user can authenticate; another user cannot read or modify their conversations.

## 3. Connect the frontend and prove chat plumbing

- [ ] Scaffold Vite + React + TypeScript while preserving the existing `.npmrc` and agent instructions; configure React Router, Tailwind, shadcn/ui, and the import alias.
- [ ] Add central frontend environment validation and the shared Supabase browser client. Only public configuration belongs in the browser.
- [ ] Build login, logout, protected routes, session restoration, and expired-session handling.
- [ ] Build the shared native-fetch API client with automatic bearer-token injection and clear HTTP/network error handling.
- [ ] Add backend endpoints to create/list threads and read ordered message history; enforce thread ownership on every operation.
- [ ] Add `POST /chat/stream` with a deterministic test response in the protocol supported by the installed Vercel AI SDK UI version.
- [ ] Connect a minimal chat screen, input, message list, and thread sidebar to FastAPI using the AI SDK React primitives.
- [ ] Persist completed test turns and restore them after page reload. Define failure/cancellation behavior so partial answers are never stored as successful turns.
- [ ] Verify invalid payloads, unknown threads, forbidden threads, upstream failures, and interrupted streams are handled clearly.

**Gate:** Log in → create a chat → see a streamed test answer → reload and recover history → log out. This milestone does not yet use the LLM.

## 4. Prepare documents for retrieval

- [ ] Review the SEC downloader's identifying user-agent, request pacing, and error handling before additional downloads.
- [ ] Parse one filing into normalized Markdown while preserving headings, tables, units, fiscal periods, source URL, accession number, and citation locations.
- [ ] Inspect extracted financial tables against the original filing: keep row labels, column years, units, and footnotes associated with the values.
- [ ] Store normalized documents and metadata in Supabase; use a stable identifier so rerunning ingestion does not create duplicates.
- [ ] Implement token-aware chunking with useful section boundaries, limited overlap, and enough context to interpret tables.
- [ ] Store chunk text, ordering, source offsets, page/section metadata, and company/year/filing-type metadata.
- [ ] Generate embeddings with the configured model and dimensions; batch requests, handle transient failures, and record enough progress to resume.
- [ ] Make refresh/re-chunk behavior explicit so outdated chunks cannot remain mixed with new ones.
- [ ] Test extraction/chunking edge cases and idempotent ingestion; inspect one filing end to end before processing all 25 sample filings.
- [ ] Verify corpus counts, missing embeddings, metadata completeness, and source-location accuracy after the sample run.

**Gate:** Every sample filing is searchable data, and a selected chunk can be traced back to its actual source passage.

## 5. Prove retrieval before generating answers

- [ ] Embed questions using the same embedding model and dimensions as the indexed chunks.
- [ ] Implement bounded semantic search with pgvector and lexical search with Postgres full-text search.
- [ ] Combine ranked results with Reciprocal Rank Fusion; deduplicate overlapping passages and optionally retrieve neighboring chunks.
- [ ] Support company, fiscal-year, and filing-type constraints. Distinguish fiscal years from filing dates.
- [ ] Handle comparison questions with retrieval that covers each requested company/year, rather than taking all evidence from one filing.
- [ ] Create a retrieval smoke command showing selected passages and metadata without calling the answer-generation model.
- [ ] Test ranking/fusion/filter logic without network calls, and add marked integration checks against the development database.
- [ ] Evaluate retrieval against the worksheet; inspect missing evidence and fix extraction or retrieval before changing answer prompts.

**Gate:** Simple lookup and multi-year comparison questions retrieve the passages needed to support an answer; gaps are visible.

## 6. Generate and validate grounded answers

- [ ] Add the PydanticAI agent with explicit request dependencies and typed answer, citation, and source-passage outputs.
- [ ] Expose bounded tools for searching filings and reading retrieved/neighboring chunks; keep database queries under application control.
- [ ] Instruct the agent to answer only from evidence, cite each factual claim, explain evidence gaps, and avoid stock recommendations or outside knowledge.
- [ ] Treat retrieved document text as evidence, not instructions; check behavior with instruction-like text inside a document.
- [ ] Validate that every citation references an actual passage retrieved for this turn and has accurate filing/location metadata.
- [ ] Check claim support, not only citation existence. Validate numerical units, periods, and any computed margins or comparisons against cited inputs; clearly label calculations and interpretations.
- [ ] Return an explicit insufficient-evidence answer when appropriate, and controlled failures for invalid/unsupported citations.
- [ ] Decide how validation interacts with streaming: treat in-progress output as provisional, mark it complete only after validation, and visibly invalidate failed answers. Persist only successful final results.
- [ ] Connect retrieval, generation, validation, streaming, and persistence in the chat orchestrator; support follow-up questions without trusting client-supplied ownership or citation data.
- [ ] Record model usage, latency, and failure categories; bound context size, tool calls, output size, and timeouts.
- [ ] Add unit tests for citation validation, refusal behavior, orchestration, and persistence; add marked live-model evaluations for the client questions.

**Gate:** A real browser question produces a supported answer with verifiable sources, or clearly states that the available evidence is insufficient.

## 7. Finish the analyst experience

- [ ] Render readable Markdown, comparison tables, streaming status, and distinct provisional/completed/failed states.
- [ ] Make each claim's citation open the exact underlying passage in one click, showing company, filing, fiscal year, page/approved location, and original source link.
- [ ] Restore citations and source passages correctly when reopening old conversations.
- [ ] Add useful empty states and example questions drawn from the supported corpus.
- [ ] Show clear messages for no evidence, unavailable sources, authentication expiry, network failures, and interrupted answers; avoid duplicate turns on retry.
- [ ] Manually verify keyboard use, long answers/tables, scrolling, and common browser sizes.
- [ ] Run frontend TypeScript checks, lint, and production build; use manual browser verification per frontend agent instructions.

**Gate:** An analyst can ask, verify, and revisit answers without developer assistance.

## 8. Close the client-brief gaps and validate quality

- [ ] Run all ten client example questions and record evidence coverage, factual accuracy, claim-level citations, location accuracy, latency, and cost.
- [ ] Include negative cases: unsupported companies/periods, missing figures, ambiguous questions, and claims that the filings cannot establish (especially AI causing margin improvements).
- [ ] Verify financial comparisons respect units, fiscal calendars, segment changes, and restated figures; surface limitations rather than silently comparing incompatible values.
- [ ] Review failed cases and rerun the affected evaluations after fixes. Citation presence alone is not proof of correctness.
- [ ] Extend ingestion to the brief's curated 10-K and 10-Q scope for S&P 500 companies across 2020–2025; define the company universe, inventory required filings, and report missing coverage.
- [ ] Process the broader corpus in resumable batches and verify retrieval/index performance and ingestion cost at that size. Any reduced pilot scope needs explicit client agreement.
- [ ] Recheck confidentiality with two analyst accounts and ensure the deployed bundle/logs do not expose privileged credentials.

**Gate:** The evaluation results demonstrate supported behavior and known gaps; the sample corpus is not mistaken for full client coverage.

## 9. Deploy and prepare operations

- [ ] Create Railway frontend and backend services; configure production build/start commands, health checks, and HTTPS URLs.
- [ ] Configure production secrets, exact CORS origins, and Supabase email confirmation/redirect URLs.
- [ ] Apply reviewed migrations using the correct connection mode and ingest the agreed corpus into the production database.
- [ ] Verify SPA route fallback and streamed responses through the deployed hosting stack.
- [ ] Add practical per-user request/concurrency limits, upstream timeouts, and provider spending alerts for the expected roughly 40 analysts plus partners.
- [ ] Measure concurrent usage on the chosen small/medium hosting footprint and agree acceptable answer latency before rollout.
- [ ] Document logs, troubleshooting, corpus updates, backup/restore, and application rollback; verify conversation history survives a backend restart.
- [ ] Run backend unit tests and relevant integration checks, frontend checks/build, and the full deployed login → question → citation → history flow.

**Gate:** Approved analysts can use the hosted app reliably, and one developer can maintain it using the runbook.

## 10. Pilot and definition of done

- [ ] Recruit five senior analysts and capture their baseline time spent on comparable document-intake tasks.
- [ ] Run the pilot for one week; record usage, time saved, incorrect/unsupported answers, citation problems, and feedback.
- [ ] Confirm the pilot reports at least three hours saved per analyst per week, as required by the brief.
- [ ] Resolve blocking trust/usability issues and repeat affected checks before the rollout decision.
- [ ] Obtain the pilot group's acceptance and roll out to the remaining approved analysts with a short usage guide and feedback channel.

**Done means:** The architecture works, evidence can be checked, private history remains private, and the analyst pilot meets the client's time-saving target.

## Later extensions — outside this delivery checklist

- Optional Ollama/Qwen answer generation for local development; verify tool calling, structured outputs, streaming, and quality with the selected model. Keep embeddings unchanged initially.
- Changing embedding models requires a planned re-embedding/index migration and matched query embeddings.
- Multi-organization tenancy, billing, external data, and trading recommendations remain outside the current client brief.
