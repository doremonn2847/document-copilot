# Document Copilot: analyst usage guide

Document Copilot answers questions about the SEC filings in Driftwood's corpus
and shows the passage behind every statement, so you can check it in one click.

## What it covers today

- **Corpus:** 10-K filings for Apple, Amazon, Alphabet, Microsoft and NVIDIA,
  corpus years 2021–2025. Other companies, 10-Qs and other years are not
  indexed yet; the answer says so instead of guessing.
- **Sign in** with your Driftwood email. New accounts are approved by the
  administrator before first use. Only you can see your conversations.
- **Delete a conversation** with the bin icon next to it in the sidebar. This is
  permanent; a conversation that is still answering cannot be deleted until it
  finishes.

## Asking good questions

- Name the **company** and the **filing year(s)**: "How does Amazon describe AWS
  in its 2025 10-K?" works better than "How is AWS doing?".
- Multi-company and multi-year comparisons are supported: "Compare Apple's and
  NVIDIA's supplier risks in 2023 and 2024."
- For a ratio or percentage change, name both figures and periods: "What is the
  ratio of Microsoft's gross-margin increase to its revenue increase for fiscal
  2022 compared with fiscal 2021?"
- Follow-up questions in the same conversation keep context ("What about the
  2023 filing?", "And Amazon?"). The assistant rewrites them into a full
  question and shows it as **"Answered as: …"** above the answer; if that is
  not what you meant, ask again with the company and year.
- Greetings, thanks and "what can you do?" get a short direct reply without
  searching the filings; unrelated requests (weather, coding) are declined.
- **Ctrl+Enter** sends. Use the example questions on the new-chat page to start.

## Reading an answer

- **Claims** are short statements, each with numbered citations **[1]**.
  Comparisons group them by company with year chips.
- **Click a citation** to open the source: company, form, corpus year, filing
  date, section or table, the exact quoted passage and a link to the original
  SEC filing. The page (or a range such as "pages 25–26" when the passage
  crosses a page) is the number printed in the 10-K itself. "Page unverified"
  means the passage could not be placed, for example a heading taken from the
  cover page; use the section and the SEC link.
- **"Not established"** lists what the filings shown do not establish, for
  example a trend nobody states or a figure that was not found. Treat these as
  real gaps, not errors.
- **Amber notices** appear when something needs your attention: statements were
  omitted because they could not be verified, a company or year is not in the
  corpus, or the question asks for advice or proof of a cause.

## What it will not do

- **No investment advice** ("Should I buy …?" gets a notice and facts only).
- **No causal conclusions** beyond what a filing states; it reports the
  company's own explanation and says where the filings stop.
- **No outside data** (news, prices, estimates).
- **No figures it cannot quote.** Derived numbers come only from its verified
  calculator, which currently works with amounts stated in sentences; some
  table-only calculations are refused.

## If something looks wrong

1. Open the citation and compare it with the claim.
2. Record it in the pilot feedback log (see the pilot plan) with the time, the
   question and what was wrong. Wrong facts and wrong citations matter most.
3. If you see "You have reached the question limit", wait a few minutes: each
   person can run 2 answers at once and 60 questions per hour.
