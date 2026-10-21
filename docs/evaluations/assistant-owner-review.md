# Phase-six owner evidence review

The owner confirmed all five proposed browser checks passed on 2026-10-19.
Evidence verdicts are recorded below. The owner manual-review gate is complete;
remaining technical quality checks are agent work.

## Final manual-review gate

Owner involvement: **opt in** for evidence and browser behavior review.

- [x] Azure question returns an answer in the frontend. Owner confirmed on 2026-10-19 after the contiguous-quote fix.
- [x] Inspect the Azure answer's numbered sources: do the displayed quotes support every factual claim, and does the original SEC link open the right filing?
- [x] Reload and reopen that conversation: the answer and its citations should remain intact.
- [x] Review the calculation fixture's arithmetic and source-period binding: the owner recorded “accepted after verification” below.
- [x] Guided Microsoft calculation returns the expected supported answer and citations in the frontend; owner confirmed.
- [x] Tesla 2028 returns an explicit evidence gap without invented figures or substituted companies/years; owner confirmed.
- [x] Stop → retry completes without duplicate messages or citations; owner confirmed.
- [x] F5 during generation → retry recovers without duplicate messages or citations; owner confirmed.
- [x] Connection interruption → reconnect → retry recovers correctly; owner confirmed.
- [x] Evidence verdicts for all three cases are recorded; the owner confirmed all five browser checks work as expected.

Passing this manual review completes the owner's review portion only. The full
phase-six gate also requires resolving the recorded broad answer-quality and
judge-calibration failures; see [evaluation results](assistant-results.md).

## Azure lookup

**Verdict:** accept.

What does Microsoft say Azure provides in the 2025 corpus filing?

In the 2025 filing, Microsoft describes Azure as a comprehensive set of cloud services that offers developers, IT professionals, and enterprises the freedom to build, deploy, and manage applications on any platform or device. Azure provides services through a global network of datacenters for computing, networking, storage, mobile and web application services, AI, Internet of Things, cognitive services, and machine learning. It enables customers to focus more on application development rather than managing on-premises hardware and software. Azure's revenue is primarily influenced by infrastructure-as-a-service and platform-as-a-service consumption-based services. Additionally, Azure AI offerings are highlighted as providing a competitive advantage for businesses looking to optimize and scale with AI. [1] [2]

### Source [1]

`c22e8f8d-6ec5-50b7-95e9-abff599b165e` — MSFT 10-K; corpus 2025; fiscal year unverified; page unverified.

Azure is a comprehensive set of cloud services that offer developers, IT professionals, and enterprises freedom to build, deploy, and manage applications on any platform or device. Customers can use Azure through our global network of datacenters for computing, networking, storage, mobile and web application services, AI, Internet of Things, cognitive services, and machine learning. Azure enables customers to devote more resources to development and use of applications that benefit their organizations, rather than managing on-premises hardware and software. Azure revenue is mainly affected by infrastructure-as-a-service and platform-as-a-service consumption-based services.

[Original SEC filing](https://www.sec.gov/Archives/edgar/data/789019/000095017025100235/msft-20250630.htm)

### Source [2]

`c22e8f8d-6ec5-50b7-95e9-abff599b165e` — MSFT 10-K; corpus 2025; fiscal year unverified; page unverified.

Azure AI offerings provide a competitive advantage as companies seek ways to optimize and scale their business with AI.

[Original SEC filing](https://www.sec.gov/Archives/edgar/data/789019/000095017025100235/msft-20250630.htm)

## Calculation over real SEC evidence

**Verdict:** accepted after verification.

**Earlier frontend finding (2026-10-19):** the owner reported two answering-service
failures. The owner then chose the guided numeric-fact flow. That flow now passed
two autonomous live checks, including a marked end-to-end test, returning 65.56%
with the comparison heading and both reported increases cited. The earlier
fixture verdict is preserved; the owner subsequently confirmed the new guided
flow works in the browser, including sources and persistence.

**Source clarification:** the cited 2022 filing explicitly labels the section
“Fiscal Year 2022 Compared with Fiscal Year 2021” and reports both annual
increases. It can support this question without a separate 2021 filing. An
independent reconciliation to the original 2021 filing would be a different
check. The verdict above records the owner's evidence review.

What is the ratio of Microsoft's reported gross-margin increase to revenue increase for fiscal 2022 compared with fiscal 2021? This is a ratio of annual increases, not the company's gross margin.

**Important:** this is a developer-assembled calculator/judge integration fixture using actual source chunks, not an autonomously generated answer. It proves the arithmetic and citation path, not natural-question planning quality.

Calculation: margin: MSFT / consolidated; annual gross-margin increase (fiscal 2022 compared with fiscal 2021, USD billions) and annual revenue increase (fiscal 2022 compared with fiscal 2021, USD billions) = 65.56 % [1] [2] [3]

### Source [1]

`dca204b5-c187-5dc8-8d88-62a09e01f8cd` — MSFT 10-K; corpus 2022; fiscal year unverified; page unverified.

Fiscal Year 2022 Compared with Fiscal Year 2021

[Original SEC filing](https://www.sec.gov/Archives/edgar/data/789019/000156459022026876/msft-10k_20220630.htm)

### Source [2]

`dca204b5-c187-5dc8-8d88-62a09e01f8cd` — MSFT 10-K; corpus 2022; fiscal year unverified; page unverified.

Gross margin increased $19.8 billion or 17% driven by growth across each of our segments.

[Original SEC filing](https://www.sec.gov/Archives/edgar/data/789019/000156459022026876/msft-10k_20220630.htm)

### Source [3]

`dca204b5-c187-5dc8-8d88-62a09e01f8cd` — MSFT 10-K; corpus 2022; fiscal year unverified; page unverified.

Revenue increased $30.2 billion or 18% driven by growth across each of our segments. Intelligent Cloud revenue increased driven by Azure and other cloud services. Productivity and Business Processes revenue increased driven by Office 365 Commercial and LinkedIn. More Personal Computing revenue increased driven by Search and news advertising and Windows.

[Original SEC filing](https://www.sec.gov/Archives/edgar/data/789019/000156459022026876/msft-10k_20220630.htm)

## Unsupported company/year

**Verdict:** accept.

What did Tesla report about vehicle revenue in its 2028 10-K?

TSLA / 10-K / corpus years 2028: The retrieved filings do not provide enough evidence for this target.

## Browser review complete

The owner confirmed the calculation, sources/history, unsupported-target refusal,
Stop/retry, F5/retry and connection-interruption recovery checks work as expected.
Broad client-question quality and judge calibration remain technical checks;
see [the worksheet](assistant-results.md).
