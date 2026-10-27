# Public demo launch — 2026-10-27

**Live:** [Document Copilot](https://frontend-production-e3f9.up.railway.app/login).
Choose **Try demo**; no email, password or manual approval is needed for a guest.
Regular email accounts still require approval.

The initial failure was configuration: Supabase anonymous sign-ins and the backend
demo kill switch were both disabled. No application-code change was needed.
The owner explicitly approved enabling anonymous sign-ins and two sequential,
once-only paid checks within the shared $1/day ceiling.

## Active configuration

- Supabase anonymous sign-ins: enabled and read back after reload.
- Email confirmation: remains enabled; manual identity linking remains disabled.
- Supabase anonymous signup rate: 30 requests/hour/IP, as displayed in the dashboard.
- CAPTCHA: remains disabled. No global CAPTCHA requirement was introduced.
- Railway `DEMO_ENABLED=true`, daily budget `1.00`, attempts/identity `3`,
  new admissions/day `100`; central Settings validation accepted hosted config.
- Backend deployment `297dc311-6b3d-4024-abf9-bb5529c0c860`: SUCCESS.
- Frontend deployment `8a215467-b2ff-425d-a61b-cebabb685b80` remains active.
- Application source remains `cf8589f9442426287d85bfa9f8f720e177859a13`;
  the configuration-only backend redeploy reused its existing image.

## Free verification

Real Postgres checks ran in a uniquely named disposable schema, using copied
tables/constraints and the production ledger operations with short independent
connections. The schema was dropped afterward. Production ledger balances and
existing conversations were not used as financial test fixtures.

Ten checks passed: concurrent idempotent admission; one active attempt; concurrent
reservations staying under the ceiling; duplicate settlement charging once;
unknown usage remaining reserved; three-attempt persistence across new store
instances; expired lease recovery without releasing a newer lease; original-day
settlement; financial retention after guest deletion; and accounting blocks
carrying into later days. Maximum parallel reservation calls: four. These are
ledger correctness checks, not hosted answer-capacity measurements.

Two actual Supabase anonymous sessions were admitted through the real FastAPI
handlers while hosted admission was still disabled. Subsequent direct REST checks
proved each guest could read only its own profile/thread and the shared SEC
corpus, could not edit profile flags, and could not access any of the four private
ledger tables. Cross-guest API history, rename and delete were rejected. Each
guest's thread list excluded other guests and existing registered-user histories.

Hosted guest history persistence, feedback save/change/remove, manual rename,
title search and disposable-chat deletion passed without additional provider
requests or attempt consumption. The original three normal profiles were retained.

The in-app browser's Try demo button opened a third isolated guest workspace with
three attempts remaining and no conversations from other identities. Reload
restored that same guest session. Guest tokens exist only in local ignored test
artifacts during verification; no credentials are included in this report.

## Two approved paid checks

| Question | Result | Elapsed | Citations | Attempts used |
|---|---|---:|---:|---:|
| Hello! What can I do with this app? | Committed app-help reply | 34.21 s | 0, conversational route | 1 |
| What does Microsoft's 2025 filing say Azure provides? Cite the supporting passages. | Committed filing answer | 93.21 s | 3 | 1 |

The Azure request emitted analyzing/searching/reading/verifying progress. All
three citation excerpts matched their stored source passages after whitespace
normalization. These checks establish the demo flow for these two cases, not a
general answer-accuracy score or a new latency guarantee.

At readback after both questions, the application ledger recorded **$0.019643
charged, $0 reserved** at conservative uncached rates (not an invoice readback), no accounting
block, daily ceiling $1.00 and three admitted guest profiles. Ten provider HTTP
requests were metered: six GPT-5.4-mini, three GPT-4o-mini and one
text-embedding-3-small. No extra model reruns were made. Both paid-test identities
had two attempts remaining; the browser-only identity retained three.

## Limits and remaining limitations

Three attempts are per anonymous identity, not per person. Clearing browser data
can create a fresh identity and lose access to previous guest history. The shared
daily budget remains the monetary boundary; conservative reservations can refuse
work before actual spend reaches $1. Existing regular accounts are outside it.

CAPTCHA and automatic anonymous-account cleanup are not implemented. Signup rate
limits and the 100/day admitted-profile ceiling do not prevent distributed signup
abuse or cap Supabase/Railway costs. Review storage and anonymous MAU usage if the
link is promoted beyond internship reviewers. Full backup/restore and hosted
six/twelve-answer capacity checks remain deferred. No human pilot/time-saving
result is claimed. Completed replay retains offline regression coverage; this
launch did not repeat a paid turn to test replay or Stop during live generation.

To stop public generation, set Railway backend `DEMO_ENABLED=false` and redeploy
that service. Keep the additive schema and financial ledger; do not refund
uncertain reservations or delete ledger records as a rollback shortcut.
