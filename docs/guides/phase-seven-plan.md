# Phase 7 plan: analyst experience

Autopilot plan for the night of 2026-10-22 (owner asleep until 06:00 +07:00).
The checklist and gate live in [todos](../todos.md#7-finish-the-analyst-experience).
Gate: *an analyst can ask, verify and revisit answers without developer
assistance.* The owner's morning browser check decides the gate; the agent
cannot open a browser, so tasks end at code, offline tests and builds.

## Rules for each autopilot iteration

- Work on the first unchecked task below. Keep changes small; follow the
  `AGENTS.md` files (no frontend test runner; frontend checks are
  `pnpm exec tsc -b`, `pnpm lint`, `pnpm build`; backend offline tests are
  `uv run --locked python -m pytest -m "not integration" -q`).
- After a task passes its checks, commit locally (don't push), tick it here
  with a one-line result, and restart the dev servers so the morning test runs
  the latest code.
- Paid OpenAI calls only through `data/chunks/assistant/capped_question.py`,
  which enforces the owner's 200-request grant in `autopilot-ledger.json`.
  Prefer replaying recorded answers offline.
- Stop at 06:00 +07:00. Then delete the temporary grant (memory note and
  ledger note) and write the morning summary at the end of this file.

## Tasks

1. [x] **Structured answer parts.** Done: `data-answer` blocks streamed, persisted and restored; text part unchanged (367 backend tests). The backend currently streams one text block.
   Add a `data-answer` part listing each claim (text, kind, company/year label,
   citation numbers) and each gap/notice (label, message, kind). Keep the text
   part for compatibility; persist it with the message parts so history
   restores it. Old messages without the part fall back to text rendering.
2. [x] **Readable answer layout.** Done: notices as banners, comparison facts grouped by company with year chips, gaps under "Not established"; old messages fall back to text. Render `data-answer`: claims grouped by
   company with year labels, gaps as distinct "not established" callouts,
   server notices (advice, omitted statements, nothing retrieved) as banners.
   Clear provisional/completed/failed states.
3. [x] **One-click citations.** Done: [n] buttons open, scroll to and focus the source, which shows form, filing date, years, page/section, excerpt and SEC link. Citation markers become buttons that open and
   scroll to the matching source, showing company, form, filing date, corpus
   year, fiscal year (unverified), page or "page unverified", section, excerpt
   and the SEC link. Keyboard-accessible.
4. [x] **Robust history.** Done: malformed stored parts are skipped, null bodies tolerated, missing cited sources shown as unavailable; text-only messages unchanged. A malformed stored citation must not hide a whole
   thread: skip it and show "source unavailable". Verify old (stub/text-only)
   and new messages both render.
5. [x] **Empty state and example questions.** Done: corpus scope note plus four one-click examples, each answered live and checked against its quotes (38 paid requests). The new-chat page lists example
   questions validated live tonight (paid, capped), one click to ask.
6. [x] **Clear failure messages.** Done: an approved user stays in the workspace when a refocus re-check fails transiently (401 still signs out, 403 still moves to pending); existing per-failure messages reviewed and kept. Auth expiry during a stream, network loss,
   interrupted answers and "no evidence" answers each get a specific message
   and a next step. Stop a transient `/auth/me` failure on tab refocus from
   unmounting the workspace (onboarding finding).
7. [x] **Accessibility and layout.** Done: unique composer ids, Ctrl/Cmd+Enter to send, focusable citation and example buttons, tighter spacing on narrow screens. Needs the owner's manual keyboard/size check. Unique ids per mounted composer, focus
   order, aria labels for sources, long answers and narrow (mobile) widths.
8. [x] **Ratio regression (correctness, found tonight).** Fixed: growth rates restating a currency change ("$19.8 billion or 17%") are offered only when the question asks for rates; live rerun returns 65.56% (6 paid requests) and is now an example question. The Microsoft ratio
   question now uses growth percentages (94.44%) instead of dollar increases
   (65.56%). Reproduce offline from `autopilot-ex-msft-ratio.json`, fix
   deterministically, then confirm with at most two capped paid runs.
9. [x] **Sales-vs-supply-chain false claim (found tonight).** Fixed: a structural check requires the subject of "majority/most/% of X" to appear in the claim's own quotes; live rerun (6 paid requests) withheld the repeated false claim and showed the coverage line for Apple 2023. Not caught: unquoted descriptors such as "large and complex" (judge-only). Analyse
   `autopilot-ex-supplier.json`; fix only if a deterministic or narrowly
   scoped check exists, otherwise record the analysis for the owner.
10. [x] **AI search planning.** Fixed: full-text search now matches any two keywords ranked by how many match (ANDing every word found nothing when passages say "artificial intelligence"), filtered form names and question words (mention, disclosure) are dropped from keywords, fact claims whose quotes share no wording fail structurally (the judge had accepted a quote of just "Item 8."), the judge assesses claims rather than the question premise, and unwarranted gaps are dropped on the final attempt when every claim passed. Live: accepted with three cited AI-risk facts after 7 diagnostic runs (57 paid requests). "Does Apple's 2025 10-K say nothing about AI?"
   searched for R&D wording. Make "does X mention Y" questions search for Y,
   then confirm with capped paid runs.

## Morning summary

(Written by the autopilot at the end of the night.)

### Findings logged during the night

- 01:00, example validation (38 paid requests, capped driver, production
  settings). Verified correct against quotes: Azure lookup, AWS description,
  Alphabet AI risks, NVIDIA Data Center demand.
- **Wrong answer accepted (comparison):** "Compare Apple's and NVIDIA's supplier
  and manufacturing risks in corpus years 2023 and 2024." Claim 0 said a
  majority of Apple's *supply chain* is outside the U.S.; its quotes say a
  majority of *net sales*. The judge accepted it.
- **Regression (calculation):** the Microsoft ratio question returned 94.44%
  (17% / 18% growth rates) instead of 65.56% ($19.8B / $30.2B) accepted on
  2026-10-19; the input judge accepted the percentage inputs, and the
  rendered labels are garbled. Both are excluded from the example list.
