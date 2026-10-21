import asyncio

import pytest

from app.assistant.deps import TurnRegistry
from app.assistant.outputs import AnswerClaim, EvidenceGap, EvidenceRef, GroundedAnswer
from app.assistant.rendering import render_answer
from app.grounding.judge import SupportDecision, SupportReport, judge_answer
from tests.assistant.test_contracts import assertions_for, passage
from tests.assistant.test_orchestrator import Agent


@pytest.mark.parametrize(
    "claim",
    [
        "The filing never mentions Azure.",
        "The report does not discuss Azure.",
        "The document contains no reference to Azure.",
        "Azure is not mentioned anywhere in the filing.",
        "There is no mention of Azure in the document.",
        "Based on these excerpts, the filing never mentions Azure.",
    ],
)
def test_excerpt_cannot_authorize_whole_filing_absence_even_with_accepting_judge(claim):
    p = passage("The company launched an AI service.")
    registry = TurnRegistry()
    registry.expose(p, p.text)
    answer = GroundedAnswer(
        status="answered",
        claims=[
            AnswerClaim(
                text=claim,
                evidence=[EvidenceRef(chunk_id=p.chunk_id, exact_quote=p.text)],
            )
        ],
    )
    judge = Agent(
        [
            SupportReport(
                decisions=[
                    SupportDecision(
                        claim_index=0,
                        evidence_assessment="The excerpt omits Azure.",
                        supported=True,
                        assertions=assertions_for(p.text),
                        reason="supported",
                    )
                ]
            )
        ]
    )
    result = asyncio.run(
        judge_answer("What does the filing say about Azure?", answer, registry, judge)
    )
    assert not result.decisions[0].supported
    assert result.decisions[0].reason == "unsupported_fact"
    assert judge.calls == []


@pytest.mark.parametrize(
    "text",
    [
        "The retrieved excerpts do not establish Azure revenue.",
        "The retrieved passage from the filing does not mention Azure.",
        "The company states it does not manufacture semiconductors.",
        "The filing states the company does not manufacture chips.",
    ],
)
def test_source_disclosed_negatives_and_scoped_limitations_still_reach_judge(text):
    p = passage(text)
    registry = TurnRegistry()
    registry.expose(p, p.text)
    answer = GroundedAnswer(
        status="answered",
        claims=[
            AnswerClaim(
                text=text,
                evidence=[EvidenceRef(chunk_id=p.chunk_id, exact_quote=p.text)],
            )
        ],
    )
    judge = Agent(
        [
            SupportReport(
                decisions=[
                    SupportDecision(
                        claim_index=0,
                        evidence_assessment="Fixture supported.",
                        supported=True,
                        assertions=assertions_for(p.text),
                        reason="supported",
                    )
                ]
            )
        ]
    )
    result = asyncio.run(judge_answer("Read the disclosure", answer, registry, judge))
    assert result.decisions[0].supported and len(judge.calls) == 1


def test_urgency_gap_renders_specific_detail_without_empty_target_colon():
    from app.retrieval.types import SearchFilters

    detail = (
        "The retrieved evidence is too sparse to support a year-by-year urgency trend."
    )
    answer = GroundedAnswer(
        status="insufficient_evidence",
        gaps=[
            EvidenceGap(
                target=SearchFilters(),
                request_quote="Does wording show increased urgency?",
                missing_detail=detail,
                reason="unsupported_causality",
            )
        ],
    )
    result = render_answer(answer, TurnRegistry())
    assert detail in result.text
    assert "causal relationship" not in result.text
    assert not result.text.startswith(":")


@pytest.mark.parametrize("target_count", [1, 10])
def test_supplier_topic_after_long_unrelated_prefix_is_exposed_without_stock_table(
    target_count,
):
    from app.assistant.tools import expose_groups
    from tests.assistant.test_tools import deps

    text = (
        "Product competition remains intense. " * 85
        + "We depend on third-party manufacturing suppliers. We face concentration risks in our supply chain."
    )
    p = passage(text).model_copy(
        update={
            "source_context": ["| Nasdaq 100 | 2025 |\n|---|---|\n| Return | 196.94 |"]
        }
    )
    d = deps()
    d.question = "supplier concentration third-party manufacturing"
    groups = [("Target", [p])] + [
        (f"Other target {i}", [passage("Other source details. " * 60)])
        for i in range(target_count - 1)
    ]
    output = expose_groups(d, groups, focus="supplier concentration manufacturing")
    quotes = [r.exact_quote for r in d.registry.evidence_refs.values()]
    assert any("third-party manufacturing suppliers" in q for q in quotes)
    assert not any("Nasdaq" in q for q in quotes)
    assert len(output) <= d.settings.assistant_tool_chars
    for ref in d.registry.evidence_refs.values():
        d.registry.verify(ref)


def test_supported_cross_filing_superlative_still_requires_semantic_judging():
    from app.grounding.validator import structural_errors

    registry = TurnRegistry()
    refs = []
    for ticker in ("AAPL", "NVDA"):
        for year in (2021, 2025):
            p = passage("Supplier dependence was disclosed.").model_copy(
                update={"ticker": ticker, "corpus_year": year}
            )
            registry.expose(p, p.text)
            refs.append(EvidenceRef(chunk_id=p.chunk_id, exact_quote=p.text))
    answer = GroundedAnswer(
        status="answered",
        claims=[
            AnswerClaim(
                text="Across filings, Apple's and NVIDIA's wording is most explicit in the later sources.",
                kind="interpretation",
                evidence=refs,
            )
        ],
    )
    # Structural coverage permits the claim; entailment remains the judge's job.
    assert structural_errors(answer, registry, searches=1) == []


def test_saved_supplier_superlative_needs_more_than_one_filing_per_company():
    from app.grounding.validator import structural_errors

    a = passage("We depend on single-source suppliers.").model_copy(
        update={"ticker": "AAPL", "corpus_year": 2021}
    )
    n = passage("We use a fabless manufacturing strategy.").model_copy(
        update={"ticker": "NVDA", "corpus_year": 2021}
    )
    registry = TurnRegistry()
    refs = []
    for p in [a, n]:
        registry.expose(p, p.text)
        refs.append(EvidenceRef(chunk_id=p.chunk_id, exact_quote=p.text))
    answer = GroundedAnswer(
        status="answered",
        claims=[
            AnswerClaim(
                text="Across the retrieved filings, Apple's 2021 wording is the most explicit about supplier dependence, while NVIDIA's 2021 wording is the most explicit about manufacturing dependence.",
                kind="interpretation",
                evidence=refs,
            )
        ],
    )
    assert any(
        "comparison" in error
        for error in structural_errors(answer, registry, searches=1)
    )


def test_prechecked_absence_keeps_correct_indices_for_other_judged_claims():
    p = passage("The company launched an AI service.")
    registry = TurnRegistry()
    registry.expose(p, p.text)
    evidence = [EvidenceRef(chunk_id=p.chunk_id, exact_quote=p.text)]
    answer = GroundedAnswer(
        status="answered",
        claims=[
            AnswerClaim(text="The filing never mentions Azure.", evidence=evidence),
            AnswerClaim(text=p.text, evidence=evidence),
        ],
    )
    judge = Agent(
        [
            SupportReport(
                decisions=[
                    SupportDecision(
                        claim_index=0,
                        evidence_assessment="Supported AI launch.",
                        supported=True,
                        assertions=assertions_for(p.text),
                        reason="supported",
                    )
                ]
            )
        ]
    )
    result = asyncio.run(judge_answer("Describe the company", answer, registry, judge))
    assert [(d.claim_index, d.supported) for d in result.decisions] == [
        (0, False),
        (1, True),
    ]


def test_financial_table_keeps_units_and_period_context_when_focus_matches():
    from app.assistant.tools import expose_groups
    from tests.assistant.test_tools import deps

    table = "| USD millions | 2025 |\n|---|---|\n| Revenue | 281,724 |"
    p = passage("Revenue, = 281,724.").model_copy(
        update={"source_context": ["Fiscal Year 2025", table]}
    )
    d = deps()
    result = expose_groups(d, [("Target", [p])], focus="gross margin revenue")
    assert table in result and "Fiscal Year 2025" in result
    for ref in d.registry.evidence_refs.values():
        d.registry.verify(ref)


def test_whole_filing_absence_is_repaired_to_scoped_gap_before_any_judge_call():
    from app.chat.orchestrator import run_grounded
    from tests.assistant.test_tools import deps

    d = deps()
    d.completed_retrievals = 1
    d.settings.openai_agent_request_limit = 20
    d.settings.assistant_grounding_repairs = 1
    d.settings.assistant_max_claims = 20
    d.settings.assistant_claim_refs = 5
    p = passage("The company launched an AI service.")
    d.registry.expose(p, p.text)
    unsafe = GroundedAnswer(
        status="answered",
        claims=[
            AnswerClaim(
                text="The filing never mentions Azure.",
                evidence=[EvidenceRef(chunk_id=p.chunk_id, exact_quote=p.text)],
            )
        ],
    )
    safe = GroundedAnswer(
        status="insufficient_evidence",
        gaps=[
            EvidenceGap(
                reason="missing_evidence",
                missing_detail="The retrieved excerpts do not establish what the filing says about Azure.",
            )
        ],
    )
    agent, judge = Agent([unsafe, safe]), Agent([])
    result = asyncio.run(
        run_grounded("What does the filing say about Azure?", [], d, agent, judge)
    )
    assert result.answer == safe
    assert len(agent.calls) == 2 and not judge.calls
    assert "never mentions" not in result.reply.text


def test_file_wide_absence_cannot_bypass_validation_inside_gap_detail():
    from app.grounding.validator import structural_errors

    answer = GroundedAnswer(
        status="insufficient_evidence",
        gaps=[
            EvidenceGap(
                reason="missing_evidence",
                missing_detail="The filing never mentions Azure.",
            )
        ],
    )
    assert any(
        "selected excerpts cannot establish absence" in error
        for error in structural_errors(answer, TurnRegistry(), searches=1)
    )
