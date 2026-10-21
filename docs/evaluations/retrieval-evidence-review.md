# Retrieval evidence review

Owner involvement: opt in. Implementation and live checks are verified; the owner accepted both evidence examples on 2026-10-18. The phase-5 sample evidence-review gate is passed.

## 1. Simple lookup

Question: What cloud services does Microsoft Azure offer to customers?

Top passage: `c22e8f8d-6ec5-50b7-95e9-abff599b165e`; MSFT 10-K; corpus year 2025. Fiscal year and page are unverified.

Source: https://www.sec.gov/Archives/edgar/data/789019/000095017025100235/msft-20250630.htm

> Azure is a comprehensive set of cloud services that offer developers, IT professionals, and enterprises freedom to build, deploy, and manage applications on any platform or device. Customers can use Azure through our global network of datacenters for computing, networking, storage, mobile and web application services, AI, Internet of Things, cognitive services, and machine learning. Azure enables customers to devote more resources to development and use of applications that benefit their organizations, rather than managing on-premises hardware and software. Azure revenue is mainly affected by infrastructure-as-a-service and platform-as-a-service consumption-based services.
> Azure AI offerings provide a competitive advantage as companies seek ways to optimize and scale their business with AI. We offer supercomputing power for AI at scale to run large workloads, complemented by our rapidly expanding portfolio of AI cloud services (including the latest models) and hardware, which includes custom-built silicon and strong partnerships with chip manufacturers. Azure AI Foundry is a unified 

[Excerpt clipped for review; full text is in `data/chunks/retrieval/azure-lookup.json`.]

Review: does this passage explain Azure services well enough to support an answer?

Yes, the retrieved passage is understandable and answerable.

## 2. Multi-year comparison

Question: For Apple, how does supplier concentration or dependence on third-party manufacturing appear across the 2021–2025 corpus filings?

These are the Apple targets from client question Q07 (the full run also retrieves NVIDIA). Each target retains three primary candidates independently. Years below are corpus folder years; fiscal years and original pages remain unverified.

### Corpus year 2021

Candidate rank 1: `a1bf6952-b82f-5072-99d7-c839a42d3ef6`; chunk 13.

Source: https://www.sec.gov/Archives/edgar/data/320193/000032019321000105/aapl-20210925.htm

> roduct defects and experiences an unanticipated product defect liability from time to time. While the Company relies on its partners to adhere to its supplier code of conduct, violations of the supplier code of conduct occur from time to time and can materially adversely affect the Company's business, reputation, results of operations and financial condition.
> The Company relies on single-source outsourcing partners in the U.S., Asia and Europe to supply and manufacture many components, and on outsourcing partners primarily located in Asia, for final assembly of substantially all of the Company's hardware products. Any failure of these partners to perform can have a negative impact on the Company's cost or supply of components or finished goods. In addition, manufacturing or logistics in these locations or transit to final destinations can

[Excerpt clipped for review; full text is retained in the JSON report.]

### Corpus year 2022

Candidate rank 1: `d95ed082-8eb2-59aa-9123-48f5878ab3ab`; chunk 8.

Source: https://www.sec.gov/Archives/edgar/data/320193/000032019322000108/aapl-20220924.htm

> tures and applications within their products, or collaborate to offer integrated solutions that are more competitive than those they currently offer.
> Supply of Components
> Although most components essential to the Company's business are generally available from multiple sources, certain components are currently obtained from single or limited sources. The Company also competes for various components with other participants in the markets for smartphones, personal computers, tablets, wearables and accessories. Therefore, many components used by the Company, including those that are available from multiple sources, are at times subject to industry-wide shortage and significant commodity pricing fluctuations.
> The Company uses some custom components that are not commonly used by its competitors, and new products introduced by the Company often

[Excerpt clipped for review; full text is retained in the JSON report.]

### Corpus year 2023

Candidate rank 1: `a5f599b8-5d9b-5347-9b23-346d97908246`; chunk 12.

Source: https://www.sec.gov/Archives/edgar/data/320193/000032019323000106/aapl-20230930.htm

> companies that have significant technical, marketing, distribution and other resources, as well as established hardware, software and digital content supplier relationships. In addition, some of the Company's competitors have broader product lines, lower-priced products and a larger installed base of active devices. Competition has been particularly intense as competitors have aggressively cut prices and lowered product margins. Certain competitors have the resources, experience or cost structures to provide products at little or no profit or even at a loss. Some of the markets in which the Company competes have from time to time experienced little to no growth or contracted overall.
> Additionally, the Company faces significant competition as competitors imitate the Company's product features and applications within their products or colla

[Excerpt clipped for review; full text is retained in the JSON report.]

### Corpus year 2024

Candidate rank 1: `e17b306f-eb43-5805-8f8b-ae0ca8af611d`; chunk 8.

Source: https://www.sec.gov/Archives/edgar/data/320193/000032019324000123/aapl-20240928.htm

> tures and applications within their products, or collaborate to offer integrated solutions that are more competitive than those they currently offer.
> Supply of Components
> Although most components essential to the Company's business are generally available from multiple sources, certain components are currently obtained from single or limited sources. The Company also competes for various components with other participants in the markets for smartphones, personal computers, tablets, wearables and accessories. Therefore, many components used by the Company, including those that are available from multiple sources, are at times subject to industry-wide shortage and significant commodity pricing fluctuations.
> The Company uses some custom components that are not commonly used by its competitors, and new products introduced by the Company often

[Excerpt clipped for review; full text is retained in the JSON report.]

### Corpus year 2025

Candidate rank 1: `5cb20df8-521e-572a-8317-8d76ef7931e0`; chunk 13.

Source: https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/aapl-20250927.htm

> in addition to sourcing from partners and facilities located in the U.S. The Company relies on single-source partners in the U.S., Asia and Europe to supply and manufacture many components, and on partners primarily located in Asia, for final assembly of substantially all of the Company's hardware products. The Company has also outsourced much of its transportation and logistics management. While these arrangements can lower operating costs, they also reduce the Company's direct control over production and distribution. Such diminished control has from time to time had, and may in the future have, an adverse effect on the cost, quality or quantity of products manufactured or services provided, or adversely affect the Company's flexibility to respond to changing conditions. Although arrangements with these partners may contain provisions f

[Excerpt clipped for review; full text is retained in the JSON report.]

Review: can you identify supplier/manufacturing risk evidence for each requested year, and see which periods or details still need more reading? It is fine to flag a weak candidate; no automatic claim about wording becoming more urgent is made.

I think the retrieved documents are good and ready.

## Acceptance

- [x] Owner reviewed the Azure lookup.
- [x] Owner reviewed the Apple comparison and identified evidence gaps.

The approved phase-5 evidence-review gate is accepted based on the owner's verdicts above. This accepts the Azure lookup and Apple comparison examples; it does not label every candidate in the ten-question worksheet as relevant. No phase-6 answering agent or browser integration has been implemented.
