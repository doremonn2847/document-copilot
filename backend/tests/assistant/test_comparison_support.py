"""Regressions from owner-reported financial and supplier comparisons."""

import asyncio

import pytest

from app.assistant.deps import TurnRegistry
from app.assistant.outputs import AnswerClaim, EvidenceRef, GroundedAnswer
from app.grounding.validator import structural_errors
from app.retrieval.types import SearchFilters
from tests.assistant.test_contracts import passage


def comparison(text, sources, *, kind="interpretation"):
    registry = TurnRegistry()
    refs = []
    documents = {}
    for ticker, year, quote in sources:
        p = passage(quote).model_copy(update={"ticker": ticker, "corpus_year": year})
        p = p.model_copy(
            update={"document_id": documents.setdefault((ticker, year), p.document_id)}
        )
        registry.expose(p, quote)
        refs.append(EvidenceRef(chunk_id=p.chunk_id, exact_quote=quote))
    return registry, GroundedAnswer(
        status="answered",
        claims=[AnswerClaim(text=text, kind=kind, evidence=refs)],
    )


def test_supplier_interpretation_cannot_borrow_nvidia_sources_from_other_claims():
    registry, answer = comparison(
        "The retrieved Apple and NVIDIA wording shows recurring supplier and manufacturing risk language, but it does not establish increased urgency over time.",
        [
            (
                "AAPL",
                2022,
                "Manufacturing is concentrated in a small number of partners.",
            )
        ],
    )
    nvda = passage(
        "Dependency on third-party suppliers reduces our control."
    ).model_copy(update={"ticker": "NVDA", "corpus_year": 2025})
    registry.expose(nvda, nvda.text)
    answer = answer.model_copy(
        update={
            "claims": [
                *answer.claims,
                AnswerClaim(
                    text="NVIDIA depends on third-party suppliers.",
                    evidence=[
                        EvidenceRef(chunk_id=nvda.chunk_id, exact_quote=nvda.text)
                    ],
                ),
            ]
        }
    )
    assert any(
        "NVDA" in error for error in structural_errors(answer, registry, searches=1)
    )


def test_cross_company_interpretation_can_cite_both_companies():
    registry, answer = comparison(
        "Apple and NVIDIA disclose supplier dependence.",
        [
            ("AAPL", 2022, "We depend on suppliers."),
            ("NVDA", 2025, "We depend on suppliers."),
        ],
    )
    assert structural_errors(answer, registry, searches=1) == []


@pytest.mark.parametrize(
    "text,quotes",
    [
        (
            "Microsoft's 2025 filing reports revenue of 281,724 and gross margin of 193,893.",
            ["Revenue, = 281,724.", "Gross margin, = 193,893."],
        ),
        ("Revenue for fiscal 2025 was USD 281,724 million.", ["Revenue, = 281,724."]),
        (
            "Revenue for fiscal 2025 was USD 281,724 million.",
            ["Revenue for fiscal 2025 was $281,724."],
        ),
        (
            "Revenue was USD 245,122 million for the prior column shown in the same table.",
            ["Revenue, = 245,122.", "USD millions."],
        ),
        (
            "The displayed table shows a 15% revenue change and a 13% gross margin change.",
            ["Revenue, = 15%.", "Gross margin, = 13%."],
        ),
    ],
)
def test_financial_comparison_rejects_unbound_figures(text, quotes):
    registry, answer = comparison(
        text, [("MSFT", 2025, q) for q in quotes], kind="fact"
    )
    assert structural_errors(answer, registry, searches=1)


def test_financial_claim_accepts_explicit_unit_and_period_quotes_from_one_filing():
    registry, answer = comparison(
        "Revenue for fiscal 2025 was USD 281,724 million.",
        [("MSFT", 2025, "Fiscal 2025. USD millions. Revenue, = 281,724.")],
        kind="fact",
    )
    assert structural_errors(answer, registry, searches=1) == []


@pytest.mark.parametrize(
    "text",
    [
        "In 2025, revenue was USD 281,724 million.",
        "Revenue (2025): USD 281,724 million.",
        "Revenue for FY2025 was USD 281,724 million.",
    ],
)
def test_source_backed_period_does_not_require_fixed_prose_template(text):
    registry, answer = comparison(
        text,
        [("MSFT", 2025, "Fiscal Year 2025. USD millions. Revenue: 281,724.")],
        kind="fact",
    )
    assert structural_errors(answer, registry, searches=1) == []


def test_missing_quoted_year_is_not_filled_from_corpus_metadata():
    registry, answer = comparison(
        "In 2025, revenue was USD 281,724 million.",
        [("MSFT", 2025, "USD millions. Revenue: 281,724.")],
        kind="fact",
    )
    assert any(
        "financial figures require" in e
        for e in structural_errors(answer, registry, searches=1)
    )


def test_parenthesized_year_heading_does_not_change_accounting_negative_amounts():
    from decimal import Decimal

    from app.grounding.validator import numeric_tokens

    assert numeric_tokens("Revenue (2025):") == {Decimal(2025)}
    assert numeric_tokens("Revenue was (2025) dollars.") == {Decimal(-2025)}


@pytest.mark.parametrize("supported", [True, False])
def test_natural_year_wording_reaches_judge_instead_of_false_fallback(supported):
    from app.chat.orchestrator import GroundingRejected, run_grounded
    from app.grounding.judge import SupportDecision, SupportReport
    from tests.assistant.test_orchestrator import Agent
    from tests.assistant.test_tools import deps

    registry, answer = comparison(
        "In 2025, revenue was USD 281,724 million.",
        [("MSFT", 2025, "Fiscal Year 2025. USD millions. Revenue: 281,724.")],
        kind="fact",
    )
    d = deps()
    d.registry = registry
    d.completed_retrievals = 1
    d.settings.openai_agent_request_limit = 20
    d.settings.assistant_grounding_repairs = 0
    d.settings.assistant_max_claims = 20
    d.settings.assistant_claim_refs = 5
    agent, judge = (
        Agent([answer]),
        Agent(
            [
                SupportReport(
                    decisions=[
                        SupportDecision(
                            claim_index=0,
                            evidence_assessment="Explicit source fiscal year, currency scale and amount agree.",
                            supported=supported,
                            reason="supported"
                            if supported
                            else "unit_or_period_mismatch",
                        )
                    ]
                )
            ]
        ),
    )
    if supported:
        result = asyncio.run(
            run_grounded("Report fiscal 2025 revenue", [], d, agent, judge)
        )
        assert result.answer == answer
    else:
        with pytest.raises(GroundingRejected):
            asyncio.run(run_grounded("Report fiscal 2025 revenue", [], d, agent, judge))
    assert len(agent.calls) == len(judge.calls) == 1


def test_descriptive_filing_lookup_does_not_need_fiscal_periods():
    registry, answer = comparison(
        "Microsoft's 2025 filing describes Azure as a comprehensive set of cloud services.",
        [("MSFT", 2025, "Azure is a comprehensive set of cloud services.")],
    )
    assert structural_errors(answer, registry, searches=1) == []


def test_filing_form_is_not_a_financial_amount_in_azure_description():
    registry, answer = comparison(
        "Microsoft's 2025 10-K says Azure revenue is affected by consumption-based services.",
        [("MSFT", 2025, "Azure revenue is affected by consumption-based services.")],
        kind="fact",
    )
    assert structural_errors(answer, registry, searches=1) == []


def test_factual_disclosure_can_name_another_company_without_citing_its_filing():
    registry, answer = comparison(
        "NVIDIA identifies Microsoft as a customer.",
        [("NVDA", 2025, "Microsoft is a customer.")],
        kind="fact",
    )
    assert structural_errors(answer, registry, searches=1) == []


def test_percentage_period_date_is_not_a_currency_amount():
    registry, answer = comparison(
        "Revenue increased 15% for the year ended June 30, 2025.",
        [("MSFT", 2025, "Revenue increased 15% for the year ended June 30, 2025.")],
        kind="fact",
    )
    assert structural_errors(answer, registry, searches=1) == []


def test_unitless_percentage_comparison_passes_with_explicit_periods():
    registry, answer = comparison(
        "Revenue increased 15% in fiscal 2025 compared with fiscal 2024.",
        [
            (
                "MSFT",
                2025,
                "Fiscal 2025 compared with fiscal 2024: revenue increased 15%.",
            )
        ],
    )
    assert structural_errors(answer, registry, searches=1) == []


def test_existing_repair_flow_blocks_bad_comparison_before_judge():
    from app.assistant.outputs import EvidenceGap
    from app.chat.orchestrator import run_grounded
    from tests.assistant.test_orchestrator import Agent
    from tests.assistant.test_tools import deps

    registry, answer = comparison(
        "Microsoft's 2025 filing reports revenue of 281,724.",
        [("MSFT", 2025, "Revenue, = 281,724.")],
        kind="fact",
    )
    d = deps()
    d.registry = registry
    d.completed_retrievals = 1
    d.settings.openai_agent_request_limit = 20
    d.settings.assistant_grounding_repairs = 1
    d.settings.assistant_max_claims = 20
    d.settings.assistant_claim_refs = 5
    corrected = GroundedAnswer(
        status="insufficient_evidence",
        gaps=[
            EvidenceGap(
                target=SearchFilters(ticker="MSFT", corpus_years=[2025]),
                reason="ambiguous_figures",
            )
        ],
    )
    agent, judge = Agent([answer, corrected]), Agent([])
    result = asyncio.run(
        run_grounded("Compare fiscal revenue figures", [], d, agent, judge)
    )
    assert len(agent.calls) == 2
    assert judge.calls == []
    assert result.answer == corrected
    assert "281,724" not in result.reply.text


@pytest.mark.parametrize(
    "extra_error", [None, "same_claim_number", "other_claim_number", "invalid_quote"]
)
def test_exhausted_financial_context_repairs_return_target_gaps_only(extra_error):
    from app.chat.orchestrator import GroundingRejected, run_grounded
    from tests.assistant.test_orchestrator import Agent
    from tests.assistant.test_tools import deps

    registry, answer = comparison(
        "Microsoft's 2025 filing reports revenue of 281,724.",
        [("MSFT", 2025, "Revenue, = 281,724.")],
        kind="fact",
    )
    registry.comparison_targets = [
        SearchFilters(ticker="MSFT", corpus_years=[year]) for year in range(2021, 2026)
    ]
    # All targets must already be represented; the fallback must not conceal
    # a separate coverage/provenance failure.
    from app.assistant.outputs import EvidenceGap

    answer = answer.model_copy(
        update={
            "status": "partial",
            "gaps": [
                EvidenceGap(target=t, reason="missing_evidence")
                for t in registry.comparison_targets[:-1]
            ],
        }
    )
    first_draft = answer
    if extra_error == "same_claim_number":
        answer = answer.model_copy(
            update={
                "claims": [
                    answer.claims[0].model_copy(
                        update={"text": "Microsoft reports revenue of 999,999."}
                    )
                ]
            }
        )
    elif extra_error == "other_claim_number":
        answer = answer.model_copy(
            update={
                "claims": [
                    *answer.claims,
                    AnswerClaim(
                        text="There are 999 customers.",
                        evidence=answer.claims[0].evidence,
                    ),
                ]
            }
        )
    elif extra_error == "invalid_quote":
        answer = answer.model_copy(
            update={
                "claims": [
                    answer.claims[0].model_copy(
                        update={
                            "evidence": [
                                answer.claims[0]
                                .evidence[0]
                                .model_copy(
                                    update={
                                        "exact_quote": "Revenue, = 281,724. Invented source text."
                                    }
                                )
                            ],
                        }
                    )
                ]
            }
        )
    d = deps()
    d.registry = registry
    d.completed_retrievals = 1
    d.settings.openai_agent_request_limit = 20
    d.settings.assistant_grounding_repairs = 1
    d.settings.assistant_max_claims = 20
    d.settings.assistant_claim_refs = 5
    agent, judge = Agent([first_draft, answer]), Agent([])
    if extra_error in ("other_claim_number", "invalid_quote"):
        with pytest.raises(GroundingRejected):
            asyncio.run(
                run_grounded("Compare fiscal 2021–2025 figures", [], d, agent, judge)
            )
    else:
        result = asyncio.run(
            run_grounded("Compare fiscal 2021–2025 figures", [], d, agent, judge)
        )
        assert result.answer.status == "insufficient_evidence"
        assert result.answer.claims == []
        assert [g.target for g in result.answer.gaps] == registry.comparison_targets
        assert all(g.reason == "ambiguous_figures" for g in result.answer.gaps)
        assert "281,724" not in result.reply.text
        assert "999,999" not in result.reply.text
        assert not any(part["type"] == "data-citation" for part in result.reply.parts)
    assert len(agent.calls) == 2
    assert not judge.calls
